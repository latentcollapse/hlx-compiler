//! Vulkan context management
//!
//! Handles instance, device, and queue initialization.
//! Manages shader module caching for HLX determinism.

use ash::{vk, Entry, Instance, Device};
use pyo3::prelude::*;
use std::collections::HashMap;
use std::collections::hash_map::DefaultHasher;
use std::ffi::CString;
use std::hash::{Hash, Hasher};

use crate::error::VulkanErrorKind;
use crate::shader::ShaderModule;
use crate::validation;

/// Manages Vulkan instance, device, and shader cache.
///
/// This is the main entry point for HLX Vulkan operations.
/// It provides content-addressed shader caching where the same
/// SPIR-V binary always produces the same shader ID.
///
/// # Python Example
///
/// ```python
/// from hlx_vulkan import VulkanContext
///
/// # Create context (auto-selects first GPU)
/// ctx = VulkanContext()
/// print(f"Using: {ctx.device_name}")
///
/// # Load shader (returns content-addressed ID)
/// shader_id = ctx.load_shader(spirv_bytes, "main")
///
/// # Second load of same bytes returns same ID (cache hit)
/// assert ctx.load_shader(spirv_bytes, "main") == shader_id
/// assert ctx.is_shader_cached(shader_id)
///
/// # Cleanup
/// ctx.cleanup()
/// ```
#[pyclass]
pub struct VulkanContext {
    /// GPU device name (e.g., "NVIDIA GeForce RTX 5060")
    #[pyo3(get)]
    pub device_name: String,

    /// Vulkan API version (e.g., "1.4.312")
    #[pyo3(get)]
    pub api_version: String,

    // Internal Vulkan state (not exposed to Python)
    #[allow(dead_code)]
    entry: Entry,
    instance: Instance,
    #[allow(dead_code)]
    physical_device: vk::PhysicalDevice,
    device: Device,
    #[allow(dead_code)]
    compute_queue: vk::Queue,
    #[allow(dead_code)]
    compute_queue_family: u32,

    // HLX-specific: content-addressed shader cache
    // Key: hex hash of SPIR-V bytes
    // Value: compiled VkShaderModule wrapper
    shader_cache: HashMap<String, ShaderModule>,

    // Track cleanup state
    cleaned_up: bool,
}

#[pymethods]
impl VulkanContext {
    /// Create a new Vulkan context.
    ///
    /// Initializes Vulkan instance, selects a physical device,
    /// creates a logical device with a compute queue.
    ///
    /// # Arguments
    ///
    /// * `device_index` - GPU index (0 = first available, default)
    /// * `enable_validation` - Enable Vulkan validation layers (default: false)
    ///
    /// # Returns
    ///
    /// VulkanContext instance ready for shader loading.
    ///
    /// # Raises
    ///
    /// * `RuntimeError` - If Vulkan initialization fails
    #[new]
    #[pyo3(signature = (device_index=0, enable_validation=false))]
    pub fn new(device_index: usize, enable_validation: bool) -> PyResult<Self> {
        log::info!(
            "Initializing VulkanContext (device_index={}, validation={})",
            device_index,
            enable_validation
        );

        // Load Vulkan entry points
        let entry = unsafe { Entry::load() }
            .map_err(|e| VulkanErrorKind::EntryLoadFailed(e.to_string()))?;

        // Create instance
        let instance = Self::create_instance(&entry, enable_validation)?;

        // Select physical device
        let (physical_device, device_name, api_version) =
            Self::select_physical_device(&instance, device_index)?;

        // Create logical device and get compute queue
        let (device, compute_queue, compute_queue_family) =
            Self::create_logical_device(&instance, physical_device)?;

        log::info!(
            "VulkanContext initialized: {} (Vulkan {})",
            device_name,
            api_version
        );

        Ok(Self {
            device_name,
            api_version,
            entry,
            instance,
            physical_device,
            device,
            compute_queue,
            compute_queue_family,
            shader_cache: HashMap::new(),
            cleaned_up: false,
        })
    }

    /// Load a shader from SPIR-V binary.
    ///
    /// Uses content-addressed caching: identical SPIR-V bytes always
    /// return the same shader ID, and the second load is a cache hit.
    ///
    /// # Arguments
    ///
    /// * `spirv_bytes` - SPIR-V binary as bytes
    /// * `entry_point` - Shader entry point name (usually "main")
    ///
    /// # Returns
    ///
    /// Shader ID (16-character hex string). Use this ID for:
    /// - Cache checks with `is_shader_cached()`
    /// - Future pipeline creation (Phase 2)
    ///
    /// # Raises
    ///
    /// * `RuntimeError` - If SPIR-V is invalid or shader creation fails
    pub fn load_shader(&mut self, spirv_bytes: &[u8], entry_point: &str) -> PyResult<String> {
        // Generate content-addressed ID from SPIR-V bytes
        let shader_id = Self::compute_shader_id(spirv_bytes);

        // Check cache first
        if self.shader_cache.contains_key(&shader_id) {
            log::debug!("Shader cache HIT: {}", shader_id);
            return Ok(shader_id);
        }

        log::debug!("Shader cache MISS: {} (loading)", shader_id);

        // Validate SPIR-V before passing to Vulkan
        validation::validate_spirv(spirv_bytes)
            .map_err(|e| VulkanErrorKind::InvalidSpirv(e))?;

        // Create shader module
        let shader_module = ShaderModule::new(
            &self.device,
            spirv_bytes,
            entry_point.to_string(),
        )?;

        // Cache it
        self.shader_cache.insert(shader_id.clone(), shader_module);

        log::info!(
            "Shader loaded: {} (entry={}, size={}, cache_size={})",
            shader_id,
            entry_point,
            spirv_bytes.len(),
            self.shader_cache.len()
        );

        Ok(shader_id)
    }

    /// Check if a shader is in the cache.
    ///
    /// # Arguments
    ///
    /// * `shader_id` - Shader ID returned by `load_shader()`
    ///
    /// # Returns
    ///
    /// True if the shader is cached, False otherwise.
    pub fn is_shader_cached(&self, shader_id: &str) -> bool {
        self.shader_cache.contains_key(shader_id)
    }

    /// Get current shader cache size.
    ///
    /// # Returns
    ///
    /// Number of cached shader modules.
    pub fn cache_size(&self) -> usize {
        self.shader_cache.len()
    }

    /// Clear the shader cache.
    ///
    /// Destroys all cached VkShaderModule objects and frees GPU resources.
    pub fn clear_cache(&mut self) {
        log::info!("Clearing shader cache ({} entries)", self.shader_cache.len());
        for (id, module) in self.shader_cache.drain() {
            log::debug!("Destroying cached shader: {}", id);
            module.destroy(&self.device);
        }
    }

    /// Get GPU memory information.
    ///
    /// # Returns
    ///
    /// Dict with:
    /// - `heap_count`: Number of memory heaps
    /// - `heap_sizes_bytes`: List of heap sizes in bytes
    pub fn get_memory_info(&self, py: Python<'_>) -> PyResult<PyObject> {
        let props = unsafe {
            self.instance
                .get_physical_device_memory_properties(self.physical_device)
        };

        let heaps: Vec<u64> = props.memory_heaps[..props.memory_heap_count as usize]
            .iter()
            .map(|h| h.size)
            .collect();

        let dict = pyo3::types::PyDict::new_bound(py);
        dict.set_item("heap_count", props.memory_heap_count)?;
        dict.set_item("heap_sizes_bytes", heaps)?;

        Ok(dict.into())
    }

    /// Clean up Vulkan resources.
    ///
    /// **Must be called before the context is dropped.**
    ///
    /// Destroys all cached shaders, the logical device, and the instance.
    /// After calling this, the context cannot be used.
    pub fn cleanup(&mut self) {
        if self.cleaned_up {
            log::warn!("VulkanContext.cleanup() called twice");
            return;
        }

        log::info!("Cleaning up VulkanContext");

        // Destroy cached shaders first
        self.clear_cache();

        // Destroy Vulkan objects in reverse order of creation
        unsafe {
            self.device.destroy_device(None);
            self.instance.destroy_instance(None);
        }

        self.cleaned_up = true;
        log::info!("VulkanContext cleanup complete");
    }
}

// Private implementation methods
impl VulkanContext {
    /// Create Vulkan instance with optional validation layers.
    fn create_instance(entry: &Entry, enable_validation: bool) -> Result<Instance, VulkanErrorKind> {
        let app_name = CString::new("HLX Vulkan Runtime").unwrap();
        let engine_name = CString::new("HLX").unwrap();

        let app_info = vk::ApplicationInfo::default()
            .application_name(&app_name)
            .application_version(vk::make_api_version(0, 1, 0, 0))
            .engine_name(&engine_name)
            .engine_version(vk::make_api_version(0, 1, 0, 0))
            .api_version(vk::API_VERSION_1_2);

        // Optionally enable validation layers
        let layer_names: Vec<CString> = if enable_validation {
            log::info!("Enabling Vulkan validation layers");
            vec![CString::new("VK_LAYER_KHRONOS_validation").unwrap()]
        } else {
            vec![]
        };
        let layer_ptrs: Vec<*const i8> = layer_names.iter().map(|l| l.as_ptr()).collect();

        let create_info = vk::InstanceCreateInfo::default()
            .application_info(&app_info)
            .enabled_layer_names(&layer_ptrs);

        let instance = unsafe { entry.create_instance(&create_info, None) }.map_err(|e| {
            VulkanErrorKind::InitializationFailed(format!("vkCreateInstance failed: {:?}", e))
        })?;

        log::debug!("Vulkan instance created");
        Ok(instance)
    }

    /// Select a physical device (GPU) by index.
    fn select_physical_device(
        instance: &Instance,
        device_index: usize,
    ) -> Result<(vk::PhysicalDevice, String, String), VulkanErrorKind> {
        let devices = unsafe { instance.enumerate_physical_devices() }.map_err(|e| {
            VulkanErrorKind::InitializationFailed(format!(
                "enumerate_physical_devices failed: {:?}",
                e
            ))
        })?;

        if devices.is_empty() {
            return Err(VulkanErrorKind::NoSuitableDevice);
        }

        log::info!("Found {} Vulkan device(s)", devices.len());

        // Log all devices for debugging
        for (i, &dev) in devices.iter().enumerate() {
            let props = unsafe { instance.get_physical_device_properties(dev) };
            let name = unsafe {
                std::ffi::CStr::from_ptr(props.device_name.as_ptr())
                    .to_string_lossy()
                    .to_string()
            };
            log::debug!("  Device {}: {}", i, name);
        }

        // Select requested device
        let device = devices
            .get(device_index)
            .copied()
            .ok_or(VulkanErrorKind::NoSuitableDevice)?;

        let props = unsafe { instance.get_physical_device_properties(device) };

        let device_name = unsafe {
            std::ffi::CStr::from_ptr(props.device_name.as_ptr())
                .to_string_lossy()
                .to_string()
        };

        let api_version = format!(
            "{}.{}.{}",
            vk::api_version_major(props.api_version),
            vk::api_version_minor(props.api_version),
            vk::api_version_patch(props.api_version)
        );

        log::info!("Selected device {}: {} (API {})", device_index, device_name, api_version);

        Ok((device, device_name, api_version))
    }

    /// Create logical device with compute queue.
    fn create_logical_device(
        instance: &Instance,
        physical_device: vk::PhysicalDevice,
    ) -> Result<(Device, vk::Queue, u32), VulkanErrorKind> {
        let queue_families =
            unsafe { instance.get_physical_device_queue_family_properties(physical_device) };

        // Find a queue family with compute support
        let compute_family = queue_families
            .iter()
            .enumerate()
            .find(|(_, props)| props.queue_flags.contains(vk::QueueFlags::COMPUTE))
            .map(|(i, _)| i as u32)
            .ok_or_else(|| {
                VulkanErrorKind::InitializationFailed(
                    "No compute queue family found".to_string()
                )
            })?;

        log::debug!("Using queue family {} for compute", compute_family);

        let queue_priorities = [1.0f32];
        let queue_create_info = vk::DeviceQueueCreateInfo::default()
            .queue_family_index(compute_family)
            .queue_priorities(&queue_priorities);

        let device_create_info =
            vk::DeviceCreateInfo::default().queue_create_infos(std::slice::from_ref(&queue_create_info));

        let device = unsafe {
            instance.create_device(physical_device, &device_create_info, None)
        }
        .map_err(|e| {
            VulkanErrorKind::InitializationFailed(format!("vkCreateDevice failed: {:?}", e))
        })?;

        let queue = unsafe { device.get_device_queue(compute_family, 0) };

        log::debug!("Logical device and compute queue created");

        Ok((device, queue, compute_family))
    }

    /// Compute content-addressed shader ID from SPIR-V bytes.
    ///
    /// Uses a fast hash for cache lookup. The actual content-addressing
    /// for HLX memoization uses BLAKE2b on the Python side.
    fn compute_shader_id(spirv_bytes: &[u8]) -> String {
        let mut hasher = DefaultHasher::new();
        spirv_bytes.hash(&mut hasher);
        format!("{:016x}", hasher.finish())
    }
}

impl Drop for VulkanContext {
    fn drop(&mut self) {
        if !self.cleaned_up {
            // This is a safety net. Users should call cleanup() explicitly.
            log::warn!(
                "VulkanContext dropped without explicit cleanup(). \
                 Call ctx.cleanup() to avoid resource leaks."
            );
            // Note: We don't call cleanup() here because it may panic
            // if the Vulkan driver is already torn down.
        }
    }
}
