"""
Integration tests for hlx_vulkan Python bindings.

These tests verify the Rust<->Python interface works correctly.
Run with: pytest python/tests/ -v
"""

import pytest


# Skip all tests if hlx_vulkan is not installed
try:
    import hlx_vulkan
    VULKAN_AVAILABLE = True
except ImportError:
    VULKAN_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not VULKAN_AVAILABLE,
    reason="hlx_vulkan not installed (run: maturin develop)"
)


class TestVulkanContextCreation:
    """Test VulkanContext initialization and properties."""

    def test_context_creation_default(self):
        """Test context creation with default parameters."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            assert ctx is not None
            assert isinstance(ctx.device_name, str)
            assert len(ctx.device_name) > 0
        finally:
            ctx.cleanup()

    def test_context_creation_with_validation(self):
        """Test context creation with validation layers enabled."""
        try:
            ctx = hlx_vulkan.VulkanContext(enable_validation=True)
            try:
                assert ctx is not None
            finally:
                ctx.cleanup()
        except RuntimeError as e:
            # Validation layers may not be installed
            if "LAYER_NOT_PRESENT" in str(e):
                pytest.skip("Vulkan validation layers not installed")
            raise

    def test_device_name_populated(self, vulkan_context):
        """Test that device_name is a non-empty string."""
        assert vulkan_context.device_name
        assert isinstance(vulkan_context.device_name, str)
        print(f"Device: {vulkan_context.device_name}")

    def test_api_version_format(self, vulkan_context):
        """Test that api_version has expected format (X.Y.Z)."""
        version = vulkan_context.api_version
        assert version
        parts = version.split(".")
        assert len(parts) == 3
        # All parts should be numeric
        for part in parts:
            assert part.isdigit()
        print(f"API Version: {version}")


class TestShaderLoading:
    """Test shader loading and caching functionality."""

    def test_load_shader_returns_id(self, vulkan_context, sample_spirv):
        """Test that load_shader returns a shader ID."""
        shader_id = vulkan_context.load_shader(sample_spirv, "main")
        assert shader_id is not None
        assert isinstance(shader_id, str)
        assert len(shader_id) == 16  # 64-bit hash as hex

    def test_shader_caching_same_id(self, vulkan_context, sample_spirv):
        """Test that same SPIR-V returns same shader ID."""
        id1 = vulkan_context.load_shader(sample_spirv, "main")
        id2 = vulkan_context.load_shader(sample_spirv, "main")

        assert id1 == id2, "Same SPIR-V should produce same shader ID"

    def test_is_shader_cached(self, vulkan_context, sample_spirv):
        """Test is_shader_cached returns True after loading."""
        shader_id = vulkan_context.load_shader(sample_spirv, "main")
        assert vulkan_context.is_shader_cached(shader_id)

    def test_is_shader_cached_unknown(self, vulkan_context):
        """Test is_shader_cached returns False for unknown ID."""
        assert not vulkan_context.is_shader_cached("nonexistent")

    def test_different_spirv_different_id(self, vulkan_context, sample_spirv):
        """Test that different SPIR-V produces different shader ID."""
        # Create a modified SPIR-V (change generator magic)
        modified = bytearray(sample_spirv)
        modified[8] = 0x42  # Change generator byte
        modified = bytes(modified)

        id1 = vulkan_context.load_shader(sample_spirv, "main")
        id2 = vulkan_context.load_shader(modified, "main")

        assert id1 != id2, "Different SPIR-V should produce different shader IDs"


class TestCacheManagement:
    """Test shader cache management."""

    def test_cache_size_starts_zero(self):
        """Test that a fresh context has empty cache."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            # Note: Session fixture may have loaded shaders
            # Use fresh context for this test
            assert ctx.cache_size() == 0
        finally:
            ctx.cleanup()

    def test_cache_size_increments(self, sample_spirv):
        """Test that cache size increases with unique shaders."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            assert ctx.cache_size() == 0

            ctx.load_shader(sample_spirv, "main")
            assert ctx.cache_size() == 1

            # Same shader shouldn't increase count
            ctx.load_shader(sample_spirv, "main")
            assert ctx.cache_size() == 1

            # Different shader should increase count
            modified = bytearray(sample_spirv)
            modified[8] = 0x42
            ctx.load_shader(bytes(modified), "main")
            assert ctx.cache_size() == 2
        finally:
            ctx.cleanup()

    def test_clear_cache(self, sample_spirv):
        """Test that clear_cache empties the cache."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            ctx.load_shader(sample_spirv, "main")
            assert ctx.cache_size() > 0

            ctx.clear_cache()
            assert ctx.cache_size() == 0
        finally:
            ctx.cleanup()


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_spirv_magic(self, vulkan_context):
        """Test that invalid SPIR-V magic is rejected."""
        invalid = bytes([0x00, 0x00, 0x00, 0x00] + [0x00] * 16)

        with pytest.raises(RuntimeError) as exc_info:
            vulkan_context.load_shader(invalid, "main")

        assert "Invalid SPIR-V" in str(exc_info.value)

    def test_spirv_too_small(self, vulkan_context):
        """Test that too-small SPIR-V is rejected."""
        too_small = bytes([0x03, 0x02, 0x23, 0x07])  # Just magic

        with pytest.raises(RuntimeError) as exc_info:
            vulkan_context.load_shader(too_small, "main")

        assert "SPIR-V" in str(exc_info.value)

    def test_spirv_not_aligned(self, vulkan_context):
        """Test that non-4-byte-aligned SPIR-V is rejected."""
        # 21 bytes - not a multiple of 4
        not_aligned = bytes([0x03, 0x02, 0x23, 0x07] + [0x00] * 17)

        with pytest.raises(RuntimeError) as exc_info:
            vulkan_context.load_shader(not_aligned, "main")

        assert "aligned" in str(exc_info.value).lower() or "SPIR-V" in str(exc_info.value)


class TestMemoryInfo:
    """Test memory information retrieval."""

    def test_get_memory_info_structure(self, vulkan_context):
        """Test that get_memory_info returns expected structure."""
        info = vulkan_context.get_memory_info()

        assert "heap_count" in info
        assert "heap_sizes_bytes" in info

        assert isinstance(info["heap_count"], int)
        assert info["heap_count"] > 0

        assert isinstance(info["heap_sizes_bytes"], list)
        assert len(info["heap_sizes_bytes"]) == info["heap_count"]

    def test_memory_info_reasonable_values(self, vulkan_context):
        """Test that memory info has reasonable values."""
        info = vulkan_context.get_memory_info()

        for heap_size in info["heap_sizes_bytes"]:
            # Each heap should be > 0 and < 1TB
            assert heap_size > 0
            assert heap_size < 1024 * 1024 * 1024 * 1024


class TestModuleMetadata:
    """Test module-level metadata."""

    def test_version_available(self):
        """Test that __version__ is available."""
        assert hasattr(hlx_vulkan, "__version__")
        assert isinstance(hlx_vulkan.__version__, str)
        # Version should be semver-like
        parts = hlx_vulkan.__version__.split(".")
        assert len(parts) >= 2

    def test_doc_available(self):
        """Test that __doc__ is available."""
        assert hasattr(hlx_vulkan, "__doc__")
        assert hlx_vulkan.__doc__ is not None
