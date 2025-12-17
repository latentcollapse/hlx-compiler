#version 450

// Cube vertex shader for HLX demo
// This shader renders a simple cube and demonstrates:
// - Deterministic vertex transforms
// - Standard Vulkan shader structure
// - Integration with HLX shader database

layout(binding = 0) uniform CubeMatrices {
    mat4 model;
    mat4 view;
    mat4 projection;
} matrices;

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec3 inColor;

layout(location = 0) out vec3 outColor;
layout(location = 1) out vec3 outNormal;
layout(location = 2) out vec3 outFragPos;

void main() {
    // Transform position to world space
    outFragPos = vec3(matrices.model * vec4(inPosition, 1.0));

    // Transform normal to world space
    outNormal = normalize(mat3(transpose(inverse(matrices.model))) * inNormal);

    // Pass through vertex color
    outColor = inColor;

    // Transform to clip space
    gl_Position = matrices.projection * matrices.view * vec4(outFragPos, 1.0);
}
