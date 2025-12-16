# Phase 1 Kickoff Checklist
## First Steps to HLX+Vulkan Integration

**Target:** Week of Dec 16-22, 2025
**Goal:** Get Vulkan environment working and load first shader

---

## Prerequisites (Do First)

### 1. Verify Vulkan SDK Installed
```bash
# Check if vulkaninfo exists
which vulkaninfo

# If missing, install:
# Ubuntu/Debian:
sudo apt install vulkan-tools vulkan-validationlayers-dev spirv-tools

# Arch Linux:
sudo pacman -S vulkan-tools vulkan-validation-layers spirv-tools

# Verify installation:
vulkaninfo | head -20
```

**Expected output:** Should show GPU name, driver version, Vulkan API version

**If this fails:** Stop here. Fix Vulkan SDK installation before proceeding.

---

### 2. Install Python Vulkan Bindings
```bash
cd /home/matt/helix-studio
source venv/bin/activate  # If using venv

pip install vulkan numpy
```

**Test installation:**
```python
python3 -c "import vulkan as vk; print(vk.VK_API_VERSION_1_0)"
```

**Expected output:** Should print an integer (e.g., `4194304`)

**If this fails:** Python `vulkan` package may be broken. Consider alternatives:
- Try `vulkan-py` instead
- Or prepare to write ctypes wrappers
- Or switch to Rust/C++ for Vulkan layer

---

### 3. Verify GPU Has Compute Queue
```bash
vulkaninfo | grep -A5 "queueCount"
```

**Expected output:** At least one queue family with `queueFlags: GRAPHICS | COMPUTE`

**If no compute queue:** Your GPU doesn't support Vulkan compute. This is rare (even integrated GPUs support it), but if you hit this, you'll need a different GPU.

---

## Day 1: Stub Implementation

### Goal: Create file structure and test imports

```bash
cd /home/matt/helix-studio

# Create stub files
touch hlx_runtime/vulkan_runtime.py
touch hlx_runtime/tests/test_vulkan_integration.py
touch hlx_runtime/spirv_validator.py
```

### Write minimal VulkanContext class

**File:** `hlx_runtime/vulkan_runtime.py`

```python
"""
HLX Vulkan Runtime
Integrates HLX with Vulkan compute pipelines.
Reference: CONTRACT_900-902
"""

import vulkan as vk
from typing import Dict, List, Optional
from .ls_ops import collapse, resolve
from .lc_codec import canonical_hash
from .errors import HLXError

class VulkanContext:
    """
    Manages Vulkan instance, device, and compute pipeline execution.
    Integrates HLX content-addressed storage with Vulkan compute.
    """

    def __init__(self, device_index: int = 0):
        """
        Initialize Vulkan context.

        Args:
            device_index: Which GPU to use (0 = first available)
        """
        print("[VulkanContext] Initializing...")

        # TODO: Create VkInstance
        self.instance = None

        # TODO: Enumerate physical devices
        self.physical_devices = []

        # TODO: Select device
        self.physical_device = None

        # TODO: Create logical device
        self.device = None

        # TODO: Get compute queue
        self.queue = None

        # TODO: Create command pool
        self.command_pool = None

        # Pipeline cache (this is where HLX magic happens!)
        self._pipeline_cache: Dict[str, vk.VkPipeline] = {}
        self._shader_modules: Dict[str, vk.VkShaderModule] = {}

        print("[VulkanContext] TODO: Actually initialize Vulkan")

    def load_shader(self, shader_handle: str) -> vk.VkShaderModule:
        """
        Load SPIR-V shader from HLX handle.
        Uses cache for idempotent loading.

        Args:
            shader_handle: HLX handle to CONTRACT_900 (VULKAN_SHADER)

        Returns:
            VkShaderModule
        """
        print(f"[VulkanContext] TODO: Load shader {shader_handle}")
        return None

    def create_compute_pipeline(self, kernel_contract: dict) -> vk.VkPipeline:
        """
        Create Vulkan compute pipeline from CONTRACT_901.
        Uses handle-based caching for idempotent compilation.

        Args:
            kernel_contract: CONTRACT_901 (COMPUTE_KERNEL)

        Returns:
            VkPipeline (may be cached from previous call)
        """
        print(f"[VulkanContext] TODO: Create pipeline")
        return None

    def execute_kernel(self, kernel_contract: dict) -> str:
        """
        Execute compute kernel from CONTRACT_901.

        Args:
            kernel_contract: CONTRACT_901 with inputs

        Returns:
            HLX handle to output buffer
        """
        print(f"[VulkanContext] TODO: Execute kernel")
        return "&h_result_placeholder"

    def cleanup(self):
        """
        Clean up Vulkan resources.
        """
        print("[VulkanContext] TODO: Cleanup")
```

### Write first test

**File:** `hlx_runtime/tests/test_vulkan_integration.py`

```python
"""
HLX Vulkan Integration Tests
Tests end-to-end: HLX handle → GPU compute → HLX result
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from hlx_runtime.vulkan_runtime import VulkanContext
    VULKAN_AVAILABLE = True
except ImportError as e:
    print(f"Vulkan not available: {e}")
    VULKAN_AVAILABLE = False

@unittest.skipUnless(VULKAN_AVAILABLE, "Vulkan not available")
class TestVulkanIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create shared VulkanContext for all tests"""
        try:
            cls.ctx = VulkanContext()
        except Exception as e:
            raise unittest.SkipTest(f"Failed to initialize Vulkan: {e}")

    def test_context_creation(self):
        """Test that VulkanContext can be created"""
        self.assertIsNotNone(self.ctx)
        print("[PASS] VulkanContext created")

    def test_shader_loading_stub(self):
        """Test shader loading (stub - will fail until implemented)"""
        # This will fail until we implement load_shader()
        # For now, just test that the method exists
        self.assertTrue(hasattr(self.ctx, 'load_shader'))
        print("[PASS] load_shader method exists")

    def test_pipeline_creation_stub(self):
        """Test pipeline creation (stub - will fail until implemented)"""
        self.assertTrue(hasattr(self.ctx, 'create_compute_pipeline'))
        print("[PASS] create_compute_pipeline method exists")

    def test_kernel_execution_stub(self):
        """Test kernel execution (stub - will fail until implemented)"""
        self.assertTrue(hasattr(self.ctx, 'execute_kernel'))
        print("[PASS] execute_kernel method exists")

if __name__ == '__main__':
    unittest.main()
```

### Run the test

```bash
cd /home/matt/helix-studio
python3 hlx_runtime/tests/test_vulkan_integration.py
```

**Expected output:**
```
[VulkanContext] Initializing...
[VulkanContext] TODO: Actually initialize Vulkan
[PASS] VulkanContext created
[PASS] load_shader method exists
[PASS] create_compute_pipeline method exists
[PASS] execute_kernel method exists
....
----------------------------------------------------------------------
Ran 4 tests in 0.001s

OK
```

**If this works:** You have a working skeleton. Proceed to Day 2.

**If this fails:** Debug import errors or Vulkan package issues.

---

## Day 2-3: Instance & Device Initialization

### Goal: Make VulkanContext.__init__ actually work

This is where it gets hard. You need to:

1. **Create VkInstance:**
   - Specify application info
   - Enable validation layers (for debugging)
   - Handle instance creation errors

2. **Enumerate Physical Devices:**
   - Use `vkEnumeratePhysicalDevices`
   - List all GPUs on system
   - Print info for debugging

3. **Select Device:**
   - Prefer discrete GPU over integrated
   - Check for compute queue support
   - Fallback to first available if no preference match

4. **Create Logical Device:**
   - Request compute queue family
   - Enable required extensions
   - Create VkDevice

5. **Get Compute Queue:**
   - Use `vkGetDeviceQueue`
   - Store queue handle for submissions

6. **Create Command Pool:**
   - Allocate command pool for compute queue family
   - Used later for recording commands

### Reference Code (Pseudocode)

```python
def _create_instance(self):
    app_info = vk.VkApplicationCreateInfo(
        sType=vk.VK_STRUCTURE_TYPE_APPLICATION_CREATE_INFO,
        pApplicationName="HLX Vulkan Runtime",
        applicationVersion=vk.VK_MAKE_VERSION(1, 0, 0),
        pEngineName="HLX",
        engineVersion=vk.VK_MAKE_VERSION(1, 0, 0),
        apiVersion=vk.VK_API_VERSION_1_0
    )

    # Enable validation layers for debugging
    layers = ["VK_LAYER_KHRONOS_validation"]

    create_info = vk.VkInstanceCreateInfo(
        sType=vk.VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        pApplicationInfo=app_info,
        enabledLayerCount=len(layers),
        ppEnabledLayerNames=layers
    )

    instance = vk.vkCreateInstance(create_info, None)
    return instance
```

**Reality check:** The Python `vulkan` package may not match this exactly. You'll need to read its docs and adapt.

### Success Criteria for Day 2-3

- [ ] `VulkanContext()` doesn't print "TODO" anymore
- [ ] Prints actual GPU name (e.g., "NVIDIA GeForce RTX 3080")
- [ ] No Vulkan errors or crashes
- [ ] `test_context_creation` still passes

---

## Day 4-5: Shader Loading

### Goal: Implement load_shader() method

```python
def load_shader(self, shader_handle: str) -> vk.VkShaderModule:
    # Check cache first
    if shader_handle in self._shader_modules:
        print(f"[VulkanContext] Shader cache hit: {shader_handle}")
        return self._shader_modules[shader_handle]

    # Resolve handle → CONTRACT_900
    shader_contract = resolve(shader_handle)
    contract_id = int(list(shader_contract.keys())[0])

    if contract_id != 900:
        raise ValueError(f"Expected CONTRACT_900, got {contract_id}")

    payload = shader_contract['900']
    spirv_bytes = payload['spirv_binary']

    # Create shader module
    create_info = vk.VkShaderModuleCreateInfo(
        sType=vk.VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        codeSize=len(spirv_bytes),
        pCode=spirv_bytes
    )

    shader_module = vk.vkCreateShaderModule(self.device, create_info, None)

    # Cache for future use
    self._shader_modules[shader_handle] = shader_module

    print(f"[VulkanContext] Shader loaded: {shader_handle}")
    return shader_module
```

### Test with Mock SPIR-V

Create a minimal test SPIR-V (or use placeholder bytes):

```python
def test_shader_loading_real(self):
    """Test shader loading with mock SPIR-V"""
    # Mock SPIR-V magic number + minimal header
    # Real SPIR-V starts with 0x07230203
    mock_spirv = b'\x03\x02\x23\x07' + b'\x00' * 100

    # Wrap in CONTRACT_900
    shader_contract = {
        '900': {
            'spirv_binary': mock_spirv,
            'entry_point': 'main',
            'shader_stage': 'compute',
            'descriptor_bindings': []
        }
    }

    # Collapse to get handle
    shader_handle = collapse(shader_contract)

    # Try to load (will create VkShaderModule)
    shader_module = self.ctx.load_shader(shader_handle)

    self.assertIsNotNone(shader_module)
    print(f"[PASS] Shader loaded: {shader_module}")
```

**Warning:** Mock SPIR-V may fail validation. You may need real SPIR-V even for testing.

### Success Criteria for Day 4-5

- [ ] `load_shader()` creates VkShaderModule
- [ ] Caching works (second call returns cached module)
- [ ] Test passes with real or mock SPIR-V

---

## Day 6-7: First Real Shader

### Goal: Compile a real GLSL compute shader to SPIR-V

**File:** `shaders/vector_add.comp`

```glsl
#version 450

layout(local_size_x = 64) in;

layout(set = 0, binding = 0) buffer InputA {
    float a[];
};

layout(set = 0, binding = 1) buffer InputB {
    float b[];
};

layout(set = 0, binding = 2) buffer Output {
    float result[];
};

void main() {
    uint index = gl_GlobalInvocationID.x;
    result[index] = a[index] + b[index];
}
```

### Compile to SPIR-V

```bash
# Install glslang if missing:
# Ubuntu: apt install glslang-tools
# Arch: pacman -S glslang

cd /home/matt/helix-studio
mkdir -p shaders

# Compile GLSL → SPIR-V
glslangValidator -V shaders/vector_add.comp -o shaders/vector_add.spv

# Verify
spirv-val shaders/vector_add.spv
```

**Expected output:** `Validation succeeded`

### Package into HLX

```bash
python3 tools/package_shader.py shaders/vector_add.spv \
    --stage compute \
    --descriptors "&h_input_a" "&h_input_b" "&h_output"
```

**Expected output:**
```
Read 1234 bytes from shaders/vector_add.spv
Validating contract...
Validation successful.
Collapsing to Latent Space...

SUCCESS: Shader packaged.
Handle: &h_shader_a7d6b60d4008efd9...
```

### Test Loading Real Shader

```python
def test_load_real_vector_add_shader(self):
    """Test loading real compiled SPIR-V shader"""
    with open('shaders/vector_add.spv', 'rb') as f:
        spirv_bytes = f.read()

    shader_contract = {
        '900': {
            'spirv_binary': spirv_bytes,
            'entry_point': 'main',
            'shader_stage': 'compute',
            'descriptor_bindings': []
        }
    }

    shader_handle = collapse(shader_contract)
    shader_module = self.ctx.load_shader(shader_handle)

    self.assertIsNotNone(shader_module)
    print(f"[PASS] Real shader loaded successfully")
```

### Success Criteria for Day 6-7

- [ ] GLSL compiles to SPIR-V without errors
- [ ] `spirv-val` confirms valid SPIR-V
- [ ] HLX can package and load real shader
- [ ] No Vulkan validation errors

---

## End of Week 1 Milestone

By end of Day 7, you should have:

- ✅ VulkanContext initializes correctly (instance, device, queue)
- ✅ Can load shaders from HLX handles (CONTRACT_900)
- ✅ Have real SPIR-V shader for vector addition
- ✅ 5+ tests passing in test_vulkan_integration.py
- ✅ Zero Vulkan validation errors

**What you DON'T have yet:**
- ❌ Pipeline creation
- ❌ Buffer management
- ❌ Kernel execution
- ❌ Actual computation results

**That's fine!** Week 1 is about proving the foundation works. Execution comes in Week 2.

---

## Debugging Tips

### Vulkan Validation Errors
If you see cryptic Vulkan errors:

```bash
# Enable validation layers (already in code)
export VK_LAYER_PATH=/usr/share/vulkan/explicit_layer.d
export VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation
```

Error messages will become much more helpful.

### Python Vulkan Package Issues
If `import vulkan` fails or behaves oddly:

1. **Check version:**
   ```bash
   pip show vulkan
   ```

2. **Try alternatives:**
   - `vulkan-py` (different package)
   - `pyVulkan` (another binding)
   - Write your own ctypes wrapper (tedious but works)

3. **Consider Rust:**
   If Python Vulkan is too painful, HLX runtime could be Rust with Python bindings (via PyO3). Rust's `vulkano` crate is excellent.

### GPU Not Detected
If `vulkaninfo` shows no devices:

1. **Check drivers:**
   ```bash
   # NVIDIA
   nvidia-smi

   # AMD
   rocm-smi

   # Intel
   vainfo
   ```

2. **Update drivers** (often fixes issues)

3. **Check kernel modules:**
   ```bash
   lsmod | grep -E 'nvidia|amdgpu|i915'
   ```

---

## When to Ask for Help

**Ask immediately if:**
- Vulkan SDK won't install
- `vulkaninfo` shows no devices after driver update
- Python `vulkan` package completely broken (no workaround)

**Debug yourself first if:**
- Validation errors (read error message carefully)
- Test failures (add print statements)
- Shader won't compile (check GLSL syntax)

---

## Summary: Week 1 Checklist

### Monday (Dec 16)
- [ ] Verify Vulkan SDK installed
- [ ] Install Python `vulkan` package
- [ ] Create stub files
- [ ] Write skeleton VulkanContext class
- [ ] Run first test (should pass with stubs)

### Tuesday-Wednesday (Dec 17-18)
- [ ] Implement VulkanContext.__init__ fully
- [ ] Test instance creation
- [ ] Test device enumeration
- [ ] Print GPU name and info
- [ ] Verify no Vulkan errors

### Thursday-Friday (Dec 19-20)
- [ ] Implement load_shader() method
- [ ] Test with mock SPIR-V
- [ ] Verify caching works
- [ ] Update tests

### Saturday-Sunday (Dec 21-22)
- [ ] Write GLSL vector_add.comp shader
- [ ] Compile to SPIR-V with glslangValidator
- [ ] Validate with spirv-val
- [ ] Package with HLX tool
- [ ] Test loading real shader
- [ ] Celebrate if everything works! 🎉

---

**Last Updated:** 2025-12-15
**Status:** Ready to start Monday morning
**Next Review:** End of Week 1 (Dec 22)
