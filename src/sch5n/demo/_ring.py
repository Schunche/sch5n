# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import override

import moderngl
import moderngl_window

VERTEX_SHADER = """
#version 330

in vec2 in_vert;

void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330

out vec4 fragColor;

uniform vec2 u_resolution;
uniform float u_time;

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);

    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);

    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));

    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float value = 0.0;
    float amp = 0.5;

    for (int i = 0; i < 5; i++) {
        value += amp * noise(p);
        p *= 2.02;
        amp *= 0.5;
    }

    return value;
}

float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

void main() {
    vec2 uv = (2.0 * gl_FragCoord.xy - u_resolution.xy) / u_resolution.y;

    float n = fbm(uv * 3.0 + vec2(u_time * 0.15, -u_time * 0.1));
    vec3 baseColor = mix(vec3(0.05, 0.08, 0.16), vec3(0.20, 0.55, 0.75), n);

    float d = abs(sdCircle(uv, 0.45)) - 0.02;
    d += (n - 0.5) * 0.06;

    float edge = 1.0 - smoothstep(0.0, 0.015, d);
    float glow = exp(-max(d, 0.0) * 18.0) * 0.6;

    vec3 col = baseColor + vec3(0.95, 0.75, 0.35) * (edge + glow);
    fragColor = vec4(col, 1.0);
}
"""


class ShaderViewer(moderngl_window.WindowConfig):  # pyright: ignore[reportPrivateImportUsage]
    gl_version = (3, 3)
    title = "Procedural GLSL Shader"
    window_size = (1280, 720)
    aspect_ratio = None

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # pyright: ignore[reportUnknownArgumentType]

        vertices = self.ctx.buffer(
            data=b"".join([
                b"\x00\x00\x80\xbf\x00\x00\x80\xbf",  # (-1, -1)
                b"\x00\x00\x80\x3f\x00\x00\x80\xbf",  # ( 1, -1)
                b"\x00\x00\x80\xbf\x00\x00\x80\x3f",  # (-1,  1)
                b"\x00\x00\x80\x3f\x00\x00\x80\x3f",  # ( 1,  1)
            ])
        )

        self.prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )

        self.vao = self.ctx.vertex_array(  # pyright: ignore[reportUnknownMemberType]
            self.prog, [(vertices, "2f", "in_vert")]
        )

    @override
    def on_render(self, time: float, frame_time: float) -> None:
        """Draw the shader."""
        self.ctx.clear()
        self.prog["u_resolution"].value = self.wnd.buffer_size  # pyright: ignore[reportAttributeAccessIssue]
        self.prog["u_time"].value = time  # pyright: ignore[reportAttributeAccessIssue]
        self.vao.render(moderngl.TRIANGLE_STRIP)


if __name__ == "__main__":
    moderngl_window.run_window_config(ShaderViewer)
