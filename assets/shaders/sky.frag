#version 330 core

// The sky behind the world: a gradient from the horizon up to the zenith,
// drawn in big pixels and a few color steps blended by ordered dithering,
// like pixel art. The gradient sits on the world's horizon with parallax.
// Deep below the surface, what shows through holes fades to the
// underground color.

uniform vec2 u_resolution;     // framebuffer size in pixels
uniform float u_scale;         // framebuffer pixels per screen pixel
uniform float u_pixel;         // size of one sky pixel, screen pixels
uniform float u_horizon_y;     // screen y of the sky's horizon, from the top
uniform float u_height;        // screen pixels from horizon to zenith
uniform float u_bands;         // color steps from horizon to zenith
uniform float u_view_top;      // world y at the top of the screen
uniform float u_world_per_px;  // world pixels per screen pixel
uniform float u_surface;       // world y of the surface
uniform vec2 u_underground;    // world pixels below the surface: start, full
uniform vec3 u_horizon;
uniform vec3 u_middle;
uniform vec3 u_zenith;
uniform vec3 u_deep;

out vec4 f_color;

// 4x4 Bayer matrix, as thresholds in [0, 1).
float bayer(vec2 cell) {
    int x = int(mod(cell.x, 4.0));
    int y = int(mod(cell.y, 4.0));
    int index = x + y * 4;
    int values[16] = int[16](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
    return (float(values[index]) + 0.5) / 16.0;
}

// Quantize `t` in [0, 1] to `steps` solid bands. Only a strip at the top
// of each band is dithered into the next, like hand made pixel art.
const float EDGE = 0.4;  // Part of a band that is dithered.

float dithered(float t, float steps, float threshold) {
    float scaled = t * steps;
    float base = floor(scaled);
    float into_edge = (scaled - base - (1.0 - EDGE)) / EDGE;
    return min(base + step(threshold, into_edge), steps) / steps;
}

vec3 sky_at(float t) {
    // Horizon to middle over the first third, then on to the zenith.
    return t < 0.35
        ? mix(u_horizon, u_middle, t / 0.35)
        : mix(u_middle, u_zenith, (t - 0.35) / 0.65);
}

void main() {
    // Screen coordinates from the top left, snapped to sky pixels.
    vec2 screen = vec2(
        gl_FragCoord.x, u_resolution.y - gl_FragCoord.y
    ) / u_scale;
    vec2 cell = floor(screen / u_pixel);
    vec2 snapped = (cell + 0.5) * u_pixel;
    float threshold = bayer(cell);

    float up = clamp((u_horizon_y - snapped.y) / u_height, 0.0, 1.0);
    // Ease out: the color changes faster near the horizon.
    up = 1.0 - (1.0 - up) * (1.0 - up);
    vec3 color = sky_at(dithered(up, u_bands, threshold));

    float world_y = u_view_top + snapped.y * u_world_per_px;
    float depth = clamp(
        (world_y - u_surface - u_underground.x)
            / (u_underground.y - u_underground.x),
        0.0,
        1.0
    );
    color = mix(color, u_deep, dithered(depth, u_bands * 0.5, threshold));

    f_color = vec4(color, 1.0);
}
