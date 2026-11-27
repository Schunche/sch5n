#version 330 core

// The sky behind the world: a smooth gradient from the horizon up to the
// zenith with a soft sun glow, sitting on the world's horizon with
// parallax. Deep below the surface, what shows through holes fades to the
// underground color.

uniform vec2 u_resolution;     // framebuffer size in pixels
uniform float u_scale;         // framebuffer pixels per screen pixel
uniform float u_horizon_y;     // screen y of the sky's horizon, from the top
uniform float u_height;        // screen pixels from horizon to zenith
uniform float u_view_top;      // world y at the top of the screen
uniform float u_world_per_px;  // world pixels per screen pixel
uniform float u_surface;       // world y of the surface
uniform vec2 u_underground;    // world pixels below the surface: start, full
uniform vec2 u_sun;            // screen position of the sun glow, 0-1
uniform float u_sun_size;      // glow radius, screen pixels
uniform vec3 u_horizon;
uniform vec3 u_middle;
uniform vec3 u_zenith;
uniform vec3 u_sun_color;
uniform vec3 u_deep;

out vec4 f_color;

// Gentle noise against 8 bit banding: invisible, but smooths the steps.
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

vec3 sky_at(float t) {
    // Bright near the horizon, then quickly into blue, deepest at the top.
    vec3 low = mix(u_horizon, u_middle, smoothstep(0.0, 0.45, t));
    return mix(low, u_zenith, smoothstep(0.3, 1.0, t));
}

void main() {
    vec2 screen = vec2(
        gl_FragCoord.x, u_resolution.y - gl_FragCoord.y
    ) / u_scale;
    vec2 size = u_resolution / u_scale;

    float up = clamp((u_horizon_y - screen.y) / u_height, 0.0, 1.0);
    vec3 color = sky_at(up);

    // A soft, wide glow around the sun that lightens the sky around it.
    vec2 sun = vec2(u_sun.x * size.x, u_horizon_y - u_sun.y * u_height);
    float dist = length(screen - sun) / u_sun_size;
    float glow = exp(-dist * dist * 1.8) * 0.45 + exp(-dist * 7.0) * 0.4;
    color += u_sun_color * glow * (1.0 - color);

    // Deep underground, what shows through holes darkens: back through
    // the sky's blues, so it stays rich instead of turning grey.
    float world_y = u_view_top + screen.y * u_world_per_px;
    float depth = smoothstep(
        u_underground.x, u_underground.y, world_y - u_surface
    );
    vec3 below = mix(sky_at(depth), u_deep, smoothstep(0.4, 1.0, depth));
    color = mix(color, below, smoothstep(0.0, 0.15, depth));

    color += (hash(gl_FragCoord.xy) - 0.5) / 255.0;
    f_color = vec4(color, 1.0);
}
