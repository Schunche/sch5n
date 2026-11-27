#version 330 core

// Animated menu background: drifting, domain warped noise in three theme
// colors, quantized to big pixels and a few color steps so it matches the
// pixel art.

in vec2 v_uv;

uniform vec2 u_resolution;  // framebuffer size in pixels
uniform float u_time;       // seconds, already scaled by the theme's speed
uniform float u_pixel;      // size of one background pixel
uniform vec3 u_dark;
uniform vec3 u_mid;
uniform vec3 u_light;

out vec4 f_color;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
        mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
        u.y
    );
}

float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 5; i++) {
        value += amplitude * noise(p);
        p = p * 2.03 + vec2(17.0, 9.0);
        amplitude *= 0.5;
    }
    return value;
}

void main() {
    // Snap to big pixels.
    vec2 pixel = floor(gl_FragCoord.xy / u_pixel) * u_pixel;
    vec2 p = pixel / u_resolution.y * 3.0;

    float t = u_time * 0.05;
    vec2 warp = vec2(
        fbm(p + vec2(0.0, t)),
        fbm(p + vec2(5.2, 1.3 - t))
    );
    float n = fbm(p + 2.5 * warp + vec2(t * 0.6, -t * 0.3));

    // A few discrete steps, like a hand made palette.
    float steps = 7.0;
    float q = floor(n * steps + 0.5) / steps;

    vec3 color = mix(u_dark, u_mid, smoothstep(0.25, 0.65, q));
    color = mix(color, u_light, smoothstep(0.62, 0.9, q) * 0.85);

    // Darker towards the bottom and the edges, so text stays readable.
    vec2 centered = v_uv - 0.5;
    float vignette = 1.0 - dot(centered, centered) * 0.9;
    color *= mix(0.55, 1.0, v_uv.y) * vignette;

    f_color = vec4(color, 1.0);
}
