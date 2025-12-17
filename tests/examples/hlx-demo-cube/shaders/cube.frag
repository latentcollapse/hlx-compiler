#version 450

// Cube fragment shader for HLX demo
// This shader demonstrates:
// - Phong lighting model (deterministic)
// - Integration with HLX shader database
// - Standard Vulkan fragment shader structure

layout(binding = 1) uniform LightingParams {
    vec3 lightPos;
    float ambientStrength;
    vec3 lightColor;
    float specularStrength;
} lighting;

layout(location = 0) in vec3 inColor;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec3 inFragPos;

layout(location = 0) out vec4 outColor;

void main() {
    // Ambient
    vec3 ambient = lighting.ambientStrength * lighting.lightColor;

    // Diffuse
    vec3 norm = normalize(inNormal);
    vec3 lightDir = normalize(lighting.lightPos - inFragPos);
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = diff * lighting.lightColor;

    // Specular
    vec3 viewDir = normalize(-inFragPos); // Camera at origin
    vec3 reflectDir = reflect(-lightDir, norm);
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), 32.0);
    vec3 specular = lighting.specularStrength * spec * lighting.lightColor;

    // Combine lighting
    vec3 result = (ambient + diffuse + specular) * inColor;
    outColor = vec4(result, 1.0);
}
