#!/bin/bash
# HLX Demo Cube Shader Compiler
# Compiles GLSL shaders to SPIR-V for Vulkan execution
#
# Prerequisites:
#   - glslc (from Vulkan SDK): brew install glslc (macOS) or pacman -S shaderc (Arch)
#   - OR glslangValidator: pacman -S vulkan-validation-layers (Arch)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/compiled"

# Create output directory
mkdir -p "${BUILD_DIR}"

# Check for shader compiler
if command -v glslc &> /dev/null; then
    echo "Using glslc compiler (recommended)"
    COMPILER="glslc"
elif command -v glslangValidator &> /dev/null; then
    echo "Using glslangValidator compiler (fallback)"
    COMPILER="glslang"
else
    echo "ERROR: No GLSL compiler found!"
    echo "Install with: sudo pacman -S vulkan-tools vulkan-validation-layers"
    exit 1
fi

# Compile vertex shader
echo "Compiling cube.vert..."
if [ "$COMPILER" = "glslc" ]; then
    glslc -c "${SCRIPT_DIR}/cube.vert" -o "${BUILD_DIR}/cube.vert.spv"
else
    glslangValidator -V -o "${BUILD_DIR}/cube.vert.spv" "${SCRIPT_DIR}/cube.vert"
fi

# Compile fragment shader
echo "Compiling cube.frag..."
if [ "$COMPILER" = "glslc" ]; then
    glslc -c "${SCRIPT_DIR}/cube.frag" -o "${BUILD_DIR}/cube.frag.spv"
else
    glslangValidator -V -o "${BUILD_DIR}/cube.frag.spv" "${SCRIPT_DIR}/cube.frag"
fi

# Verify SPIR-V magic (0x07230203 in little-endian = 03022307 in hex dump)
echo ""
echo "Verifying SPIR-V binaries..."
for file in "${BUILD_DIR}"/*.spv; do
    MAGIC=$(xxd -p -l 4 "$file")
    if [ "$MAGIC" = "03022307" ]; then
        SIZE=$(wc -c < "$file")
        echo "✓ $(basename $file) (${SIZE} bytes, magic: 0x${MAGIC})"
    else
        echo "✗ $(basename $file) INVALID MAGIC: 0x${MAGIC}"
        exit 1
    fi
done

echo ""
echo "✓ All shaders compiled successfully!"
echo "Output: ${BUILD_DIR}/"
echo ""
echo "SPIR-V binaries ready for HLX shader database:"
echo "  - cube.vert.spv (vertex shader)"
echo "  - cube.frag.spv (fragment shader)"
