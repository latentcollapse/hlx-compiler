"""
Integration tests for ShaderDatabase and VulkanContext bridge.

These tests verify the Rust<->Python interface for shader database
operations via the load_shader_from_db method.

Run with: pytest python/tests/test_shaderdb_integration.py -v
"""

import pytest
import tempfile
import sys
from pathlib import Path

# Add hlx_runtime to path for shaderdb import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hlx_runtime"))

# Skip all tests if hlx_vulkan is not installed
try:
    import hlx_vulkan
    VULKAN_AVAILABLE = True
except ImportError:
    VULKAN_AVAILABLE = False

from shaderdb import ShaderDatabase, ShaderHandle

pytestmark = pytest.mark.skipif(
    not VULKAN_AVAILABLE,
    reason="hlx_vulkan not installed (run: maturin develop)"
)


@pytest.fixture
def temp_db():
    """
    Create a temporary shader database.

    Yields a ShaderDatabase instance backed by a temporary directory.
    Cleans up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ShaderDatabase(tmpdir)
        yield db, tmpdir
        db.close()


@pytest.fixture
def sample_shader_bytes():
    """
    Provide a minimal valid SPIR-V binary for testing.

    This is the same SPIR-V header used in conftest.py - valid
    enough to pass database checks and be loaded as a shader module.
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


class TestShaderDatabaseBridge:
    """Test the bridge between Python ShaderDatabase and Rust VulkanContext."""

    def test_load_shader_from_db_basic(self, temp_db, sample_shader_bytes):
        """Test loading a shader from database via load_shader_from_db."""
        db, db_path = temp_db
        ctx = hlx_vulkan.VulkanContext()

        try:
            # Add shader to database
            handle = db.add_shader(
                sample_shader_bytes,
                name="test_shader",
                shader_stage="compute",
                entry_point="main"
            )

            # Verify shader exists in database
            assert db.exists(handle)
            assert db.get(handle) == sample_shader_bytes

            # Load shader from database via Rust
            shader_id = ctx.load_shader_from_db(str(handle), db_path)

            # Verify shader was loaded and cached
            assert shader_id is not None
            assert isinstance(shader_id, str)
            assert len(shader_id) == 16  # 64-bit hash as hex
            assert ctx.is_shader_cached(shader_id)

        finally:
            ctx.cleanup()

    def test_load_shader_from_db_returns_consistent_id(self, temp_db, sample_shader_bytes):
        """Test that loading same shader returns same shader_id (cache hit)."""
        db, db_path = temp_db
        ctx = hlx_vulkan.VulkanContext()

        try:
            # Add shader to database
            handle = db.add_shader(sample_shader_bytes, name="test_shader")

            # Load it twice via load_shader_from_db
            id1 = ctx.load_shader_from_db(str(handle), db_path)
            id2 = ctx.load_shader_from_db(str(handle), db_path)

            # Should return same ID (second call is cache hit)
            assert id1 == id2

            # Cache size should be 1, not 2
            assert ctx.cache_size() == 1

        finally:
            ctx.cleanup()

    def test_load_shader_from_db_deterministic_hash(self, temp_db, sample_shader_bytes):
        """Test that load_shader_from_db produces same ID as direct load_shader."""
        db, db_path = temp_db
        ctx = hlx_vulkan.VulkanContext()

        try:
            # Add shader to database
            handle = db.add_shader(sample_shader_bytes, name="test_shader")

            # Load via database bridge
            id_from_db = ctx.load_shader_from_db(str(handle), db_path)

            # Load the same bytes directly
            id_direct = ctx.load_shader(sample_shader_bytes, "main")

            # Both methods should produce same shader_id (content-addressed)
            assert id_from_db == id_direct
            assert ctx.cache_size() == 1  # Same shader, so cache size is 1

        finally:
            ctx.cleanup()

    def test_load_shader_from_db_multiple_shaders(self, temp_db, sample_shader_bytes):
        """Test loading multiple different shaders from database."""
        db, db_path = temp_db
        ctx = hlx_vulkan.VulkanContext()

        try:
            # Add multiple shaders to database
            modified1 = bytearray(sample_shader_bytes)
            modified1[8] = 0x42
            modified1 = bytes(modified1)

            modified2 = bytearray(sample_shader_bytes)
            modified2[8] = 0x99
            modified2 = bytes(modified2)

            handle1 = db.add_shader(modified1, name="shader_1")
            handle2 = db.add_shader(modified2, name="shader_2")
            handle3 = db.add_shader(sample_shader_bytes, name="shader_3")

            # Load all three
            id1 = ctx.load_shader_from_db(str(handle1), db_path)
            id2 = ctx.load_shader_from_db(str(handle2), db_path)
            id3 = ctx.load_shader_from_db(str(handle3), db_path)

            # All IDs should be different (different content)
            assert id1 != id2
            assert id2 != id3
            assert id1 != id3

            # Cache should have 3 entries
            assert ctx.cache_size() == 3

            # All should be cached
            assert ctx.is_shader_cached(id1)
            assert ctx.is_shader_cached(id2)
            assert ctx.is_shader_cached(id3)

        finally:
            ctx.cleanup()

    def test_load_shader_from_db_invalid_handle(self, temp_db):
        """Test that invalid handle raises error."""
        db, db_path = temp_db
        ctx = hlx_vulkan.VulkanContext()

        try:
            # Try to load non-existent shader
            invalid_handle = ShaderHandle.from_spirv(b"fake data")

            with pytest.raises(Exception):  # KeyError from db.get()
                ctx.load_shader_from_db(str(invalid_handle), db_path)

        finally:
            ctx.cleanup()

    def test_load_shader_from_db_invalid_db_path(self, sample_shader_bytes):
        """Test that invalid database path raises error."""
        ctx = hlx_vulkan.VulkanContext()

        try:
            # Try to load from non-existent database
            # ShaderHandle.from_spirv creates a valid handle for any bytes
            handle = ShaderHandle.from_spirv(sample_shader_bytes)

            with pytest.raises(Exception):  # RuntimeError from Python
                ctx.load_shader_from_db(str(handle), "/nonexistent/path/to/db")

        finally:
            ctx.cleanup()

    def test_shader_database_deduplication_with_vulkan(self, temp_db, sample_shader_bytes):
        """
        Test that ShaderDatabase deduplication works correctly.

        When adding the same SPIR-V bytes multiple times, the database
        should return the same handle (deduplication).
        """
        db, db_path = temp_db
        ctx = hlx_vulkan.VulkanContext()

        try:
            # Add same shader three times
            handle1 = db.add_shader(sample_shader_bytes, name="shader_a")
            handle2 = db.add_shader(sample_shader_bytes, name="shader_b")
            handle3 = db.add_shader(sample_shader_bytes, name="shader_c")

            # All handles should be identical (content-addressed)
            assert str(handle1) == str(handle2) == str(handle3)

            # Load via database
            shader_id = ctx.load_shader_from_db(str(handle1), db_path)

            # Loading other handles should return same shader_id (cache hit)
            assert ctx.load_shader_from_db(str(handle2), db_path) == shader_id
            assert ctx.load_shader_from_db(str(handle3), db_path) == shader_id

            # Cache should only have 1 shader
            assert ctx.cache_size() == 1

        finally:
            ctx.cleanup()


class TestShaderHandleGeneration:
    """Test that ShaderHandle generation works correctly."""

    def test_shader_handle_format(self, sample_shader_bytes):
        """Test that ShaderHandle has correct format."""
        handle = ShaderHandle.from_spirv(sample_shader_bytes)

        assert str(handle).startswith("&h_shader_")
        assert len(str(handle)) == len("&h_shader_") + 64  # 64 hex chars for BLAKE2b-256

        # Hash should be lowercase hex
        hash_part = str(handle)[len("&h_shader_"):]
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_shader_handle_deterministic(self, sample_shader_bytes):
        """Test that ShaderHandle is deterministic."""
        handle1 = ShaderHandle.from_spirv(sample_shader_bytes)
        handle2 = ShaderHandle.from_spirv(sample_shader_bytes)

        assert str(handle1) == str(handle2)

    def test_shader_handle_different_for_different_spirv(self, sample_shader_bytes):
        """Test that different SPIR-V produces different handles."""
        modified = bytearray(sample_shader_bytes)
        modified[8] = 0x42
        modified = bytes(modified)

        handle1 = ShaderHandle.from_spirv(sample_shader_bytes)
        handle2 = ShaderHandle.from_spirv(modified)

        assert str(handle1) != str(handle2)
