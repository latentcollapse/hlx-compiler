# Vulkan Phase 1 Assessment
## What Gemini Built vs What We Need

**Date:** 2025-12-15
**Context:** Gemini hit API quota mid-stream. Assessing salvageable work before Phase 1 kickoff.

---

## What Gemini Completed ✅

### 1. Contract Schemas (contracts.py)
**Status:** Complete and production-ready

```python
CONTRACT_IDS = {
    'VULKAN_SHADER': 900,
    'COMPUTE_KERNEL': 901,
    'PIPELINE_CONFIG': 902,
}

CONTRACT_SCHEMAS = {
    900: {
        'spirv_binary': (bytes, bytearray),
        'entry_point': str,
        'shader_stage': str,
        'descriptor_bindings': list
    },
    901: {
        'kernel_name': str,
        'shader_handle': str,
        'workgroup_size': list,
        'shared_memory_bytes': int,
        'push_constants_layout': str
    },
    902: {
        'pipeline_id': str,
        'stages': list,
        'sync_barriers': list,
        'output_image': str
    }
}
```

**Assessment:** This is solid. The schemas correctly map HLX contract structure to Vulkan concepts. No changes needed.

---

### 2. Extension Tests (test_extensions.py)
**Status:** Good foundation, needs expansion

**What works:**
- 4 tests validating contract structure
- Tests for all 3 Vulkan contracts (900, 901, 902)
- Tests contract wrapping/unwrapping via ls.collapse/resolve
- Tests validation error handling (missing fields)

**What's missing:**
- No actual Vulkan execution (just structure validation)
- No SPIR-V validation (spirv-val integration)
- No end-to-end tests (shader load → execute → retrieve result)

**Verdict:** Keep as-is for contract validation. Will create separate `test_vulkan_integration.py` for runtime tests.

---

### 3. SPIR-V Packaging Tool (package_shader.py)
**Status:** Complete and useful

**What it does:**
```bash
$ python tools/package_shader.py my_shader.spv --stage compute --descriptors "&h_buf_in" "&h_buf_out"
Read 1234 bytes from my_shader.spv
Validating contract...
Validation successful.
Collapsing to Latent Space...

SUCCESS: Shader packaged.
Handle: &h_shader_a7d6b60d...
Verification: Resolved matches original.
```

**Assessment:** This is exactly what we need for Phase 1. Can package any SPIR-V binary into HLX CONTRACT_900. Keep as-is.

---

## What's Missing (Phase 1 Work) ❌

### 1. Vulkan Runtime Module (CRITICAL)
**File:** `hlx_runtime/vulkan_runtime.py` (doesn't exist yet)

**Required Components:**

#### A. Instance & Device Initialization
```python
class VulkanContext:
    def __init__(self, device_index: int = 0):
        # 1. Create VkInstance
        self.instance = self._create_instance()

        # 2. Enumerate physical devices
        self.physical_devices = self._enumerate_devices()

        # 3. Select device (default: first discrete GPU)
        self.physical_device = self._select_device(device_index)

        # 4. Create logical device + compute queue
        self.device = self._create_device()
        self.queue = self._get_compute_queue()

        # 5. Create command pool
        self.command_pool = self._create_command_pool()

        # 6. Initialize pipeline cache (for HLX memoization)
        self._pipeline_cache = {}  # handle → VkPipeline
        self._shader_modules = {}  # handle → VkShaderModule
```

**Complexity:** ~200-300 lines
**Dependencies:** `vulkan` Python package (via pip)

---

#### B. Shader Loading
```python
def load_shader(self, shader_handle: str) -> VkShaderModule:
    """
    Load SPIR-V from HLX handle, create VkShaderModule.
    Uses cache for idempotent loading.
    """
    if shader_handle in self._shader_modules:
        return self._shader_modules[shader_handle]

    # Resolve handle → CONTRACT_900
    shader_contract = resolve(shader_handle)
    contract_id = int(list(shader_contract.keys())[0])

    if contract_id != 900:
        raise ValueError(f"Expected CONTRACT_900, got {contract_id}")

    payload = shader_contract['900']
    spirv_bytes = payload['spirv_binary']

    # Validate SPIR-V (optional but recommended)
    # self._validate_spirv(spirv_bytes)

    # Create shader module
    shader_module = vk.vkCreateShaderModule(
        self.device,
        vk.VkShaderModuleCreateInfo(
            codeSize=len(spirv_bytes),
            pCode=spirv_bytes
        )
    )

    self._shader_modules[shader_handle] = shader_module
    return shader_module
```

**Complexity:** ~50-100 lines
**Optional:** Add spirv-val validation for safety

---

#### C. Pipeline Creation
```python
def create_compute_pipeline(self, kernel_contract: dict) -> VkPipeline:
    """
    Create Vulkan compute pipeline from CONTRACT_901.
    Uses handle-based caching for idempotent compilation.
    """
    # Canonical hash of kernel contract
    kernel_handle = canonical_hash(kernel_contract)

    # Check cache (this is where HLX wins!)
    if kernel_handle in self._pipeline_cache:
        return self._pipeline_cache[kernel_handle]

    # Extract kernel config
    payload = kernel_contract['901']
    shader_handle = payload['shader_handle']
    entry_point = payload.get('entry_point', 'main')  # If not in 901, read from 900?

    # Load shader module
    shader_module = self.load_shader(shader_handle)

    # Create descriptor set layout (from descriptor_bindings)
    # This is complex - need to parse binding info
    descriptor_layout = self._create_descriptor_layout(shader_handle)

    # Create pipeline layout
    pipeline_layout = vk.vkCreatePipelineLayout(
        self.device,
        vk.VkPipelineLayoutCreateInfo(
            setLayoutCount=1,
            pSetLayouts=[descriptor_layout]
        )
    )

    # Create compute pipeline
    pipeline = vk.vkCreateComputePipelines(
        self.device,
        None,  # No pipeline cache initially
        1,
        vk.VkComputePipelineCreateInfo(
            stage=vk.VkPipelineShaderStageCreateInfo(
                stage=vk.VK_SHADER_STAGE_COMPUTE_BIT,
                module=shader_module,
                pName=entry_point
            ),
            layout=pipeline_layout
        )
    )

    # Cache for future use (deterministic memoization!)
    self._pipeline_cache[kernel_handle] = pipeline
    return pipeline
```

**Complexity:** ~150-200 lines (descriptor layout parsing is tricky)
**This is the HLX magic:** Same kernel contract → cache hit, no recompilation!

---

#### D. Kernel Execution
```python
def execute_kernel(self, kernel_contract: dict) -> str:
    """
    Execute compute kernel from CONTRACT_901.
    Returns handle to output buffer.
    """
    # 1. Get or create pipeline (may be cached!)
    pipeline = self.create_compute_pipeline(kernel_contract)

    # 2. Parse inputs from kernel contract
    payload = kernel_contract['901']
    input_handles = payload.get('inputs', [])

    # 3. Create buffers for inputs
    input_buffers = [self._create_buffer_from_handle(h) for h in input_handles]

    # 4. Allocate output buffer (size from kernel config or inferred)
    output_buffer = self._allocate_output_buffer(payload)

    # 5. Create descriptor set
    descriptor_set = self._bind_buffers(input_buffers + [output_buffer])

    # 6. Record command buffer
    cmd_buffer = self._create_command_buffer()
    vk.vkCmdBindPipeline(cmd_buffer, vk.VK_PIPELINE_BIND_POINT_COMPUTE, pipeline)
    vk.vkCmdBindDescriptorSets(cmd_buffer, vk.VK_PIPELINE_BIND_POINT_COMPUTE, ...)

    # Dispatch workgroups
    workgroup_size = payload['workgroup_size']
    vk.vkCmdDispatch(cmd_buffer, workgroup_size[0], workgroup_size[1], workgroup_size[2])

    vk.vkEndCommandBuffer(cmd_buffer)

    # 7. Submit to queue
    vk.vkQueueSubmit(self.queue, ...)
    vk.vkQueueWaitIdle(self.queue)

    # 8. Read back result
    result_data = self._read_buffer(output_buffer)

    # 9. Collapse result to HLX handle
    result_handle = collapse(result_data)

    return result_handle
```

**Complexity:** ~300-400 lines (buffer management is verbose in Vulkan)
**This is the payoff:** HLX input → GPU compute → HLX output (deterministic, content-addressed)

---

### 2. SPIR-V Validation Integration (RECOMMENDED)
**File:** `hlx_runtime/spirv_validator.py` (optional but good for safety)

```python
import subprocess

def validate_spirv(spirv_bytes: bytes) -> bool:
    """
    Run spirv-val on SPIR-V binary.
    Raises exception if invalid.
    """
    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix='.spv') as f:
        f.write(spirv_bytes)
        f.flush()

        # Run spirv-val
        result = subprocess.run(
            ['spirv-val', f.name],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise ValueError(f"Invalid SPIR-V: {result.stderr}")

        return True
```

**Complexity:** ~50 lines
**Benefit:** Catch malformed SPIR-V before it crashes Vulkan driver

---

### 3. Integration Tests (NEW FILE NEEDED)
**File:** `hlx_runtime/tests/test_vulkan_integration.py`

**Required Tests:**

1. **test_vulkan_context_creation**
   - Verify VulkanContext initializes without error
   - Check device enumeration works
   - Verify compute queue available

2. **test_shader_loading**
   - Load mock SPIR-V from CONTRACT_900
   - Verify VkShaderModule created
   - Test idempotent loading (same handle → cache hit)

3. **test_pipeline_creation**
   - Create pipeline from CONTRACT_901
   - Verify VkPipeline created
   - Test caching (same contract → cache hit)

4. **test_simple_compute**
   - Run "hello world" compute shader (e.g., vector addition)
   - Input: [1, 2, 3, 4]
   - Output: [2, 4, 6, 8] (multiply by 2)
   - Verify result via ls.resolve

5. **test_gemm_minimal**
   - 4×4 matrix multiplication
   - Prove correctness before scaling to 1024×1024

**Complexity:** ~200-300 lines
**Success Criteria:** All tests pass on NVIDIA, AMD, and Intel GPUs

---

## Dependency Assessment

### Python Packages Required
```bash
pip install vulkan           # Vulkan bindings
pip install numpy            # For matrix operations
pip install spirv-tools      # For spirv-val (optional)
```

### System Dependencies
- **Vulkan SDK:** Must be installed on system
  - Ubuntu: `apt install vulkan-sdk`
  - Arch: `pacman -S vulkan-devel`
- **GPU Drivers:** NVIDIA/AMD/Intel with Vulkan support
- **Validation Layers:** For debugging (VK_LAYER_KHRONOS_validation)

---

## Phase 1 Task Breakdown

### Week 1: Foundation (Dec 16-22)
- [ ] Install Vulkan Python bindings, verify system setup
- [ ] Implement VulkanContext.__init__ (instance, device, queue)
- [ ] Write test_vulkan_context_creation
- [ ] Implement load_shader() method
- [ ] Write test_shader_loading with mock SPIR-V

**Milestone:** VulkanContext can initialize and load shaders

---

### Week 2: Execution (Dec 23-29)
- [ ] Implement create_compute_pipeline() with caching
- [ ] Implement buffer management (create, bind, read)
- [ ] Implement execute_kernel() end-to-end
- [ ] Write test_simple_compute (vector addition)
- [ ] Write test_pipeline_caching (verify idempotence)

**Milestone:** Can execute simple compute shader via HLX

---

### Week 3: Polish & Validation (Dec 30 - Jan 5)
- [ ] Add spirv-val integration
- [ ] Handle errors gracefully (no GPU, invalid SPIR-V, etc.)
- [ ] Write test_gemm_minimal (4×4 matrix multiply)
- [ ] Document VulkanContext API in docstrings
- [ ] Update VERIFICATION_REPORT.md with Vulkan test results

**Milestone:** Phase 1 complete, ready for Phase 2 (GEMM benchmark)

---

## Estimated Complexity

| Component | Lines of Code | Difficulty | Dependencies |
|-----------|---------------|------------|--------------|
| VulkanContext (init) | 200-300 | Medium | Vulkan SDK |
| Shader loading | 50-100 | Easy | ls_ops.py |
| Pipeline creation | 150-200 | Hard | Descriptor layout parsing |
| Kernel execution | 300-400 | Hard | Buffer management |
| Integration tests | 200-300 | Medium | Mock SPIR-V |
| **Total** | **900-1300** | **Hard** | **Vulkan SDK, GPU** |

**Reality Check:** This is genuinely hard. Vulkan is verbose and unforgiving. Budget extra time for debugging driver issues.

---

## What NOT to Build (Yet)

### Defer to Phase 2+
- ❌ Full GEMM implementation (wait until execution works)
- ❌ Performance optimization (premature)
- ❌ Multi-GPU support (overkill for prototype)
- ❌ Transfer queues (use compute queue for everything initially)
- ❌ Push constants (use buffers for all data)

### Keep It Minimal
The goal of Phase 1 is **prove HLX can talk to Vulkan correctly**. That's it. Don't gold-plate.

---

## Risk Assessment

### Risk 1: Vulkan Python bindings are immature
**Reality:** The `vulkan` package is thin wrapper around C API. May be buggy or incomplete.
**Mitigation:** Be prepared to write ctypes wrappers for missing functions. Or switch to Rust/C++ if Python bindings are unusable.

### Risk 2: Descriptor set management is complex
**Reality:** Vulkan descriptor sets are notoriously fiddly. Easy to get wrong.
**Mitigation:** Start with simplest possible layout (1 storage buffer in, 1 out). Add complexity gradually.

### Risk 3: Driver bugs and validation errors
**Reality:** Vulkan drivers have bugs. Validation layers are strict.
**Mitigation:** Test on multiple GPUs early. Use validation layers during development. File driver bugs if necessary.

### Risk 4: SPIR-V generation is non-trivial
**Reality:** We need SPIR-V for testing. Generating it programmatically is hard.
**Mitigation:** Use glslangValidator to compile GLSL → SPIR-V. Ship pre-compiled .spv files for tests. Don't write SPIR-V by hand.

---

## Success Criteria for Phase 1

### Must Have
- [x] VulkanContext initializes on at least 1 GPU (NVIDIA or AMD)
- [ ] Can load SPIR-V from CONTRACT_900 handle
- [ ] Can create pipeline from CONTRACT_901 handle
- [ ] Can execute vector addition shader (hello world)
- [ ] Input/output via HLX handles (ls.collapse/resolve)
- [ ] 10+ integration tests passing
- [ ] Zero Vulkan validation errors

### Nice to Have
- [ ] Works on NVIDIA, AMD, and Intel GPUs
- [ ] SPIR-V validation via spirv-val
- [ ] Pipeline cache persistence (save to disk)
- [ ] Clear error messages (not raw Vulkan codes)

---

## Next Immediate Actions

1. **Install Vulkan Python bindings:**
   ```bash
   pip install vulkan numpy
   ```

2. **Verify Vulkan SDK installed:**
   ```bash
   vulkaninfo | head -20
   ```
   Should show GPU info. If not, install Vulkan SDK first.

3. **Create stub file:**
   ```bash
   touch hlx_runtime/vulkan_runtime.py
   touch hlx_runtime/tests/test_vulkan_integration.py
   ```

4. **Write VulkanContext.__init__ skeleton:**
   ```python
   class VulkanContext:
       def __init__(self):
           print("TODO: Initialize Vulkan instance")
           print("TODO: Enumerate devices")
           print("TODO: Create logical device")
   ```

5. **Test imports work:**
   ```python
   import vulkan as vk
   print(vk.VK_API_VERSION_1_0)  # Should print version number
   ```

---

## Gemini's Work: Final Verdict

**Keep:**
- ✅ contracts.py (CONTRACT_900-902 schemas) - production-ready
- ✅ test_extensions.py - good contract validation tests
- ✅ package_shader.py - useful CLI tool

**Build New:**
- ❌ vulkan_runtime.py - doesn't exist, needs ~1000 LOC
- ❌ test_vulkan_integration.py - doesn't exist, needs ~300 LOC
- ❌ spirv_validator.py - optional, but recommended

**Conclusion:** Gemini laid good groundwork (schemas + tooling), but the hard work (actual Vulkan integration) remains. Phase 1 is still 2-3 weeks of focused development.

---

**Last Updated:** 2025-12-15
**Status:** Ready to begin Phase 1 implementation
**Next Step:** Install Vulkan dependencies and verify system setup
