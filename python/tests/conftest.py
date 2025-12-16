"""
Pytest configuration and fixtures for hlx_vulkan tests.
"""

import pytest
import os


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "gpu: marks tests that require a GPU (deselect with '-m \"not gpu\"')"
    )


@pytest.fixture(scope="session")
def has_vulkan():
    """Check if Vulkan is available."""
    try:
        import hlx_vulkan
        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def vulkan_context(has_vulkan):
    """
    Provide a shared VulkanContext for all tests.

    Using session scope to avoid repeated initialization overhead.
    """
    if not has_vulkan:
        pytest.skip("hlx_vulkan not installed")

    import hlx_vulkan
    ctx = hlx_vulkan.VulkanContext()
    yield ctx
    ctx.cleanup()


@pytest.fixture
def sample_spirv():
    """
    Provide a minimal valid SPIR-V binary for testing.

    This is a header-only SPIR-V that won't execute but passes
    basic validation and can be loaded as a shader module.

    SPIR-V version word format (little-endian u32):
    - bits 0-7: 0
    - bits 8-15: minor version
    - bits 16-23: major version
    - bits 24-31: 0
    So version 1.0 = 0x00010000, stored as [0x00, 0x00, 0x01, 0x00] in LE
    """
    return bytes([
        # Magic number (0x07230203 in little-endian)
        0x03, 0x02, 0x23, 0x07,
        # Version 1.0 (0x00010000 in little-endian)
        0x00, 0x00, 0x01, 0x00,
        # Generator (0 = unknown)
        0x00, 0x00, 0x00, 0x00,
        # Bound = 1 (minimum valid)
        0x01, 0x00, 0x00, 0x00,
        # Reserved (schema = 0)
        0x00, 0x00, 0x00, 0x00,
    ])


@pytest.fixture
def real_spirv():
    """
    Load real SPIR-V from test_data if available.

    Falls back to minimal SPIR-V if no test data exists.
    """
    spirv_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "test_data", "vector_add.spv"
    )

    if os.path.exists(spirv_path):
        with open(spirv_path, "rb") as f:
            return f.read()

    # Fallback to minimal header (same as sample_spirv)
    return bytes([
        0x03, 0x02, 0x23, 0x07,  # Magic
        0x00, 0x00, 0x01, 0x00,  # Version 1.0
        0x00, 0x00, 0x00, 0x00,  # Generator
        0x01, 0x00, 0x00, 0x00,  # Bound
        0x00, 0x00, 0x00, 0x00,  # Reserved
    ])
