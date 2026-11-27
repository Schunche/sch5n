#version 330 core

// Unit quad corner, (0, 0) top left to (1, 1) bottom right.
in vec2 in_corner;

// Per instance.
in vec4 i_rect;    // x, y, width, height (world or screen pixels)
in vec4 i_uv;      // u0, v0, u1, v1
in vec4 i_color;   // tint / fill color
in vec4 i_params;  // kind, corner radius, border width, unused

uniform vec2 u_screen;  // viewport size in pixels
uniform vec2 u_offset;  // camera top left in world pixels
uniform float u_zoom;

out vec2 v_uv;
out vec4 v_color;
out vec2 v_local;  // pixel position inside the quad
flat out vec2 v_size;
flat out vec4 v_params;

void main() {
    vec2 world = i_rect.xy + in_corner * i_rect.zw;
    vec2 screen = (world - u_offset) * u_zoom;
    vec2 ndc = screen / u_screen * 2.0 - 1.0;
    gl_Position = vec4(ndc.x, -ndc.y, 0.0, 1.0);

    v_uv = mix(i_uv.xy, i_uv.zw, in_corner);
    v_color = i_color;
    v_local = in_corner * i_rect.zw;
    v_size = i_rect.zw;
    v_params = i_params;
}
