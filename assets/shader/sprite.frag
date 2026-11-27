#version 330 core

in vec2 v_uv;
in vec4 v_color;
in vec2 v_local;
flat in vec2 v_size;
flat in vec4 v_params;

uniform sampler2D u_texture;

out vec4 f_color;

const float KIND_SPRITE = 0.0;

// Signed distance to a rounded box centered on the origin.
float rounded_box(vec2 p, vec2 half_size, float radius) {
    vec2 q = abs(p) - half_size + radius;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - radius;
}

void main() {
    vec4 color;
    if (v_params.x == KIND_SPRITE) {
        color = texture(u_texture, v_uv) * v_color;
    } else {
        // Solid shape: filled rounded rectangle, or only its border.
        float radius = min(v_params.y, min(v_size.x, v_size.y) * 0.5);
        float border = v_params.z;
        vec2 half_size = v_size * 0.5;
        float dist = rounded_box(v_local - half_size, half_size, radius);
        float coverage = clamp(0.5 - dist, 0.0, 1.0);
        if (border > 0.0) {
            coverage *= clamp(dist + border + 0.5, 0.0, 1.0);
        }
        color = vec4(v_color.rgb, v_color.a * coverage);
    }
    if (color.a <= 0.0) {
        discard;
    }
    f_color = color;
}
