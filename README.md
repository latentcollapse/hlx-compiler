# hlx_vulkan

Rust+PyO3 Vulkan compute backend for HLX.

## Overview

This crate provides a professional-grade Vulkan interface for HLX, replacing Python's unreliable `vulkan` bindings with a type-safe Rust implementation exposed via PyO3.

## Features

- **Content-Addressed Shader Caching**: Same SPIR-V bytes always return the same shader ID
- **Clean Python API**: No Vulkan internals exposed to Python
- **Proper Error Handling**: Descriptive errors instead of cryptic Vulkan codes
- **Validation Support**: Optional Vulkan validation layers for debugging

## Installation

### Prerequisites

1. **Rust toolchain** (1.70+)
   ```bash
   rustup update stable
   ```

2. **Vulkan SDK**
   ```bash
   # Arch Linux
   sudo pacman -S vulkan-tools vulkan-validation-layers

   # Ubuntu/Debian
   sudo apt install vulkan-tools vulkan-validationlayers-dev
   ```

3. **maturin** (Python/Rust build tool)
   ```bash
   pip install maturin
   ```

### Build and Install

```bash
cd hlx_vulkan

# Development build (fast iteration)
maturin develop

# Or build a release wheel
maturin build --release
pip install target/wheels/hlx_vulkan-*.whl
```

## Usage

### Basic Example

```python
from hlx_vulkan import VulkanContext

# Initialize Vulkan
ctx = VulkanContext()
print(f"GPU: {ctx.device_name}")
print(f"API: {ctx.api_version}")

# Load a shader (content-addressed caching)
with open("shader.spv", "rb") as f:
    spirv = f.read()

shader_id = ctx.load_shader(spirv, "main")
print(f"Shader ID: {shader_id}")

# Second load returns same ID (cache hit)
assert ctx.load_shader(spirv, "main") == shader_id
assert ctx.is_shader_cached(shader_id)

# Cleanup
ctx.cleanup()
```

### With HLX Integration

```python
from hlx_runtime.vulkan_bridge import VulkanBridge
from hlx_runtime.ls_ops import collapse
from hlx_runtime.contracts import CONTRACT_IDS

# Create CONTRACT_900 (VULKAN_SHADER)
shader_contract = {
    str(CONTRACT_IDS['VULKAN_SHADER']): {
        'spirv_binary': spirv_bytes,
        'entry_point': 'main',
        'shader_stage': 'compute',
        'descriptor_bindings': []
    }
}

# Collapse to HLX handle
handle = collapse(shader_contract)

# Load via bridge
bridge = VulkanBridge()
shader_id = bridge.load_shader_from_hlx(handle)
```

## API Reference

### VulkanContext

The main entry point for Vulkan operations.

#### Constructor

```python
VulkanContext(device_index=0, enable_validation=False)
```

- `device_index`: GPU index (0 = first available)
- `enable_validation`: Enable Vulkan validation layers

#### Properties

- `device_name: str` - GPU name (e.g., "NVIDIA GeForce RTX 5060")
- `api_version: str` - Vulkan API version (e.g., "1.4.312")

#### Methods

- `load_shader(spirv_bytes, entry_point) -> str` - Load SPIR-V shader, returns shader ID
- `is_shader_cached(shader_id) -> bool` - Check if shader is in cache
- `cache_size() -> int` - Get number of cached shaders
- `clear_cache()` - Clear all cached shaders
- `get_memory_info() -> dict` - Get GPU memory information
- `cleanup()` - Release all Vulkan resources

## Testing

```bash
# Rust unit tests
cargo test

# Python integration tests
maturin develop
pytest python/tests/ -v
```

## Architecture

```
Python (HLX Runtime)
        |
        | PyO3 bindings
        v
Rust (hlx_vulkan)
        |
        | ash crate
        v
Vulkan Driver
        |
        v
GPU (NVIDIA/AMD/Intel)
```

## License

MIT
