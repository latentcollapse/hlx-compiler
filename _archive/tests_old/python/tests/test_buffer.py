"""
Buffer management tests for hlx_vulkan.

Tests vertex buffer creation, uniform buffer management, and data upload.
Run with: pytest python/tests/test_buffer.py -v
"""

import pytest
import struct


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


class TestVertexBufferCreation:
    """Test vertex buffer creation and data upload."""

    def test_create_vertex_buffer_basic(self):
        """Test creating a simple vertex buffer."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            # Create a simple triangle (3 vertices, 9 floats each)
            # Format: x,y,z, nx,ny,nz, r,g,b per vertex
            vertices = [
                # Vertex 0: position (0,0,0), normal (0,0,1), color (1,0,0) red
                0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
                # Vertex 1: position (1,0,0), normal (0,0,1), color (0,1,0) green
                1.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
                # Vertex 2: position (0,1,0), normal (0,0,1), color (0,0,1) blue
                0.0, 1.0, 0.0,  0.0, 0.0, 1.0,  0.0, 0.0, 1.0,
            ]

            buffer_id = ctx.create_vertex_buffer(vertices)

            # Verify buffer ID format
            assert buffer_id is not None
            assert isinstance(buffer_id, str)
            assert len(buffer_id) == 16
            # Should be hex digits
            assert all(c in "0123456789abcdef" for c in buffer_id)

        finally:
            ctx.cleanup()

    def test_create_vertex_buffer_cube(self):
        """Test creating vertex buffer with cube geometry."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            # 8 vertices of a unit cube, 9 floats each
            vertices = [
                # Front face
                -1.0, -1.0, -1.0,  0.0, 0.0, -1.0,  1.0, 0.0, 0.0,  # v0: red
                1.0, -1.0, -1.0,   0.0, 0.0, -1.0,  0.0, 1.0, 0.0,  # v1: green
                1.0, 1.0, -1.0,    0.0, 0.0, -1.0,  0.0, 0.0, 1.0,  # v2: blue
                -1.0, 1.0, -1.0,   0.0, 0.0, -1.0,  1.0, 1.0, 0.0,  # v3: yellow
                # Back face
                -1.0, -1.0, 1.0,   0.0, 0.0, 1.0,   1.0, 0.0, 1.0,  # v4: magenta
                1.0, -1.0, 1.0,    0.0, 0.0, 1.0,   0.0, 1.0, 1.0,  # v5: cyan
                1.0, 1.0, 1.0,     0.0, 0.0, 1.0,   1.0, 1.0, 1.0,  # v6: white
                -1.0, 1.0, 1.0,    0.0, 0.0, 1.0,   0.5, 0.5, 0.5,  # v7: gray
            ]

            buffer_id = ctx.create_vertex_buffer(vertices)
            assert buffer_id is not None
            assert len(buffer_id) == 16

            # Same vertices should produce same buffer ID (deterministic)
            buffer_id2 = ctx.create_vertex_buffer(vertices)
            assert buffer_id == buffer_id2

        finally:
            ctx.cleanup()

    def test_create_vertex_buffer_empty_fails(self):
        """Test that empty vertex buffer creation fails."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            with pytest.raises(RuntimeError, match="cannot be empty"):
                ctx.create_vertex_buffer([])

        finally:
            ctx.cleanup()

    def test_create_vertex_buffer_deterministic(self):
        """Test that same vertices produce same buffer ID."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            vertices = [
                0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
                1.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
            ]

            id1 = ctx.create_vertex_buffer(vertices)
            id2 = ctx.create_vertex_buffer(vertices)

            assert id1 == id2
            assert len(id1) == 16

        finally:
            ctx.cleanup()

    def test_create_vertex_buffer_different_data_different_id(self):
        """Test that different vertices produce different buffer IDs."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            vertices1 = [
                0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
                1.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
            ]

            vertices2 = [
                0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
                2.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,  # Different x
            ]

            id1 = ctx.create_vertex_buffer(vertices1)
            id2 = ctx.create_vertex_buffer(vertices2)

            assert id1 != id2

        finally:
            ctx.cleanup()


class TestUniformBufferCreation:
    """Test uniform buffer creation and updates."""

    def test_create_uniform_buffer_basic(self):
        """Test creating a uniform buffer for a 4x4 matrix."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            # 4x4 matrix = 16 floats = 64 bytes
            buffer_id = ctx.create_uniform_buffer(64)

            assert buffer_id is not None
            assert isinstance(buffer_id, str)
            assert len(buffer_id) == 16
            assert all(c in "0123456789abcdef" for c in buffer_id)

        finally:
            ctx.cleanup()

    def test_create_uniform_buffer_various_sizes(self):
        """Test creating uniform buffers of various sizes."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            sizes = [4, 16, 32, 64, 128, 256, 512]

            for size in sizes:
                buffer_id = ctx.create_uniform_buffer(size)
                assert buffer_id is not None
                assert len(buffer_id) == 16

        finally:
            ctx.cleanup()

    def test_create_uniform_buffer_zero_size_fails(self):
        """Test that zero-size uniform buffer creation fails."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            with pytest.raises(RuntimeError, match="must be > 0"):
                ctx.create_uniform_buffer(0)

        finally:
            ctx.cleanup()

    def test_create_uniform_buffer_deterministic(self):
        """Test that same size produces same buffer ID."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            id1 = ctx.create_uniform_buffer(64)
            id2 = ctx.create_uniform_buffer(64)

            assert id1 == id2

        finally:
            ctx.cleanup()


class TestUniformBufferUpdate:
    """Test uniform buffer data updates."""

    def test_update_uniform_buffer_with_matrix(self):
        """Test updating uniform buffer with identity matrix."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            buffer_id = ctx.create_uniform_buffer(64)

            # Identity matrix as 16 floats
            identity = [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ]

            # Pack as bytes
            data = b''.join(struct.pack('f', x) for x in identity)
            data_list = list(data)

            # Should not raise
            ctx.update_uniform_buffer(buffer_id, data_list)

        finally:
            ctx.cleanup()

    def test_update_uniform_buffer_scale_matrix(self):
        """Test updating uniform buffer with scale matrix."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            buffer_id = ctx.create_uniform_buffer(64)

            # Scale matrix (2x, 3x, 4x)
            scale = [
                2.0, 0.0, 0.0, 0.0,
                0.0, 3.0, 0.0, 0.0,
                0.0, 0.0, 4.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ]

            data = b''.join(struct.pack('f', x) for x in scale)
            data_list = list(data)

            ctx.update_uniform_buffer(buffer_id, data_list)

        finally:
            ctx.cleanup()

    def test_update_uniform_buffer_invalid_id(self):
        """Test that updating non-existent buffer fails."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            data = [0] * 64

            with pytest.raises(RuntimeError, match="not found"):
                ctx.update_uniform_buffer("0000000000000000", data)

        finally:
            ctx.cleanup()

    def test_update_uniform_buffer_data_too_large_fails(self):
        """Test that oversized data fails."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            buffer_id = ctx.create_uniform_buffer(32)

            # Try to write 64 bytes to 32-byte buffer
            data = [0] * 64

            with pytest.raises(RuntimeError, match="exceeds buffer size"):
                ctx.update_uniform_buffer(buffer_id, data)

        finally:
            ctx.cleanup()

    def test_update_uniform_buffer_partial_write(self):
        """Test partial update of uniform buffer (smaller than buffer)."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            buffer_id = ctx.create_uniform_buffer(64)

            # Write only 32 bytes to 64-byte buffer
            data = [42] * 32

            # Should succeed
            ctx.update_uniform_buffer(buffer_id, data)

        finally:
            ctx.cleanup()


class TestBufferCacheAndCleanup:
    """Test buffer cache management and cleanup."""

    def test_buffer_cleanup_on_context_cleanup(self):
        """Test that buffers are cleaned up when context is cleaned up."""
        ctx = hlx_vulkan.VulkanContext()

        vertices = [
            0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
            1.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
        ]

        buffer_id = ctx.create_vertex_buffer(vertices)
        assert buffer_id is not None

        # Cleanup should not raise
        ctx.cleanup()

    def test_multiple_buffers_per_context(self):
        """Test creating multiple buffers in same context."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            # Create vertex buffer
            vertices = [
                0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
                1.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
            ]
            vertex_id = ctx.create_vertex_buffer(vertices)

            # Create uniform buffer
            uniform_id = ctx.create_uniform_buffer(64)

            # Update uniform buffer
            identity = [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ]
            data = b''.join(struct.pack('f', x) for x in identity)
            data_list = list(data)
            ctx.update_uniform_buffer(uniform_id, data_list)

            # Both buffers should have valid IDs
            assert vertex_id != uniform_id
            assert len(vertex_id) == 16
            assert len(uniform_id) == 16

        finally:
            ctx.cleanup()

    def test_buffer_cache_survives_multiple_creates(self):
        """Test that buffer cache persists across multiple creates."""
        ctx = hlx_vulkan.VulkanContext()
        try:
            vertices1 = [
                0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
                1.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
            ]

            id1 = ctx.create_vertex_buffer(vertices1)

            # Create same buffer again
            id1_again = ctx.create_vertex_buffer(vertices1)

            # Both should have same ID
            assert id1 == id1_again

            # Create different buffer
            vertices2 = [
                0.0, 0.0, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
                2.0, 0.0, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
            ]
            id2 = ctx.create_vertex_buffer(vertices2)

            # Different content means different ID
            assert id1 != id2

        finally:
            ctx.cleanup()
