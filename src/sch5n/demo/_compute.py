# Copyright (c) 2026 Schunche
"""Experimental software."""

import math
import secrets
import struct
from datetime import datetime
from pathlib import Path
lazy import argparse

import moderngl
import moderngl_window
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
SHADER_PATH = BASE_DIR / "assets" / "shader" / "compute.comp"
SCREENSHOT_DIR = BASE_DIR / "captures" / "schreenshots"

FALLBACK_COMPUTE_SHADER = """#version 430

layout (local_size_x = 16, local_size_y = 16, local_size_z = 1) in;
layout (rgba32f, binding = 0) writeonly uniform image2D u_out_tex;

uniform vec2 u_resolution;
uniform float u_time;
uniform int u_seed;

// Fast, precision-safe integer hash in [0, 1)
float hash21(ivec2 cell, int seed) {
    uvec2 p = uvec2(cell);
    uint s = uint(seed);
    uint h = p.x * 374761393u + p.y * 668265263u + s * 1442695041u;
    h = (h ^ (h >> 13)) * 1274126177u;
    h = h ^ (h >> 16);
    return float(h) / 4294967295.0;
}

float noise(vec2 p, int seed) {
    ivec2 i = ivec2(floor(p));
    vec2 f = fract(p);
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);

    float a = hash21(i, seed);
    float b = hash21(i + ivec2(1, 0), seed);
    float c = hash21(i + ivec2(0, 1), seed);
    float d = hash21(i + ivec2(1, 1), seed);

    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p, int seed) {
    float val = 0.0;
    float amp = 0.5;
    for (int i = 0; i < 5; i++) {
        val += amp * noise(p, seed + i * 101);
        p *= 2.02;
        amp *= 0.5;
    }
    return val;
}

void main() {
    ivec2 gid = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(u_out_tex);
    if (gid.x >= size.x || gid.y >= size.y) {
        return;
    }

    vec2 fragCoord = vec2(gid) + 0.5;
    vec2 uv = (2.0 * fragCoord - vec2(size)) / float(size.y);

    vec2 p = uv * 2.5;

    // Domain warping driven by u_seed
    vec2 q = vec2(
        fbm(p + vec2(0.0, u_time * 0.12), u_seed),
        fbm(p + vec2(5.2, 1.3 - u_time * 0.10), u_seed + 7919)
    );
    float pattern = fbm(p + 3.2 * q + vec2(u_time * 0.08), u_seed + 104729);

    vec3 dark = vec3(0.04, 0.06, 0.12);
    vec3 mid = vec3(0.14, 0.48, 0.68);
    vec3 highlight = vec3(0.96, 0.78, 0.42);

    vec3 col = mix(dark, mid, smoothstep(0.15, 0.65, pattern));
    col = mix(col, highlight, smoothstep(0.65, 0.92, q.x * pattern * 1.4));

    imageStore(u_out_tex, gid, vec4(col, 1.0));
}
"""


class ComputeSandbox(moderngl_window.WindowConfig):  # pyright: ignore[reportPrivateImportUsage]
    gl_version = (4, 3)
    title = "GLSL Compute Sandbox"
    window_size = (1280, 720)
    aspect_ratio = None

    seed: int = secrets.randbelow(2**16)
    reset_shader: bool = False

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--seed",
            type=int,
            default=secrets.randbelow(2**16),
            help="Initial procedural generation seed (default: 1337)",
        )
        parser.add_argument(
            "--reset-shader",
            action="store_true",
            help="Overwrite assets/shader/compute.comp with the default starter shader",  # ruff: ignore[line-too-long]
        )

    def __init__(self, **kwargs) -> None:  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]  # ruff: ignore[missing-type-kwargs]
        super().__init__(**kwargs)  # pyright: ignore[reportUnknownArgumentType]

        self.seed = self.argv.seed  # pyright: ignore[reportOptionalMemberAccess]
        self.paused = False
        self.sim_time = 0.0

        SHADER_PATH.parent.mkdir(parents=True, exist_ok=True)
        if self.argv.reset_shader or not SHADER_PATH.exists():  # pyright: ignore[reportOptionalMemberAccess]
            SHADER_PATH.write_text(FALLBACK_COMPUTE_SHADER, encoding="utf-8")
            print(f"[Wrote Shader] {SHADER_PATH}")  # ruff: ignore[print]
        else:
            print(f"[Loaded Existing Shader] {SHADER_PATH}")  # ruff: ignore[print]

        vertices = struct.pack(
            "16f",
            -1.0,
            -1.0,
            0.0,
            0.0,
            1.0,
            -1.0,
            1.0,
            0.0,
            -1.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
        )
        quad_vbo = self.ctx.buffer(vertices)

        self.display_prog = self.ctx.program(
            vertex_shader="""
                #version 430
                in vec2 in_vert;
                in vec2 in_uv;
                out vec2 v_uv;
                void main() {
                    v_uv = in_uv;
                    gl_Position = vec4(in_vert, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 430
                in vec2 v_uv;
                out vec4 fragColor;
                uniform sampler2D u_tex;
                void main() {
                    fragColor = texture(u_tex, v_uv);
                }
            """,
        )
        self.display_prog["u_tex"].value = 0  # pyright: ignore[reportAttributeAccessIssue]
        self.vao = self.ctx.vertex_array(  # pyright: ignore[reportUnknownMemberType]
            self.display_prog, [(quad_vbo, "2f 2f", "in_vert", "in_uv")]
        )

        self._tex_size = (0, 0)
        self.out_tex = None
        self.compute = None
        self._last_mtime = 0.0

        self._ensure_target_texture()
        self._load_compute_shader(force=True)
        self._update_title()

    def _update_title(self) -> None:
        state = "PAUSED" if self.paused else "RUNNING"
        self.wnd.title = (
            f"GLSL Compute Sandbox | Seed: {self.seed} | {state} "
            f"[R: New Seed | S: Save PNG | Space: Pause]"
        )

    def _ensure_target_texture(self) -> None:
        w, h = self.wnd.buffer_size
        w, h = max(1, w), max(1, h)
        if (w, h) != self._tex_size or self.out_tex is None:
            if self.out_tex is not None:
                self.out_tex.release()
            self.out_tex = self.ctx.texture((w, h), 4, dtype="f4")
            self._tex_size = (w, h)

    def _load_compute_shader(self, force: bool = False) -> None:  # ruff: ignore[boolean-default-value-positional-argument, boolean-type-hint-positional-argument]
        try:
            mtime = SHADER_PATH.stat().st_mtime
        except OSError:
            return
        if not force and mtime == self._last_mtime:
            return
        try:
            source = SHADER_PATH.read_text(encoding="utf-8")
            new_compute = self.ctx.compute_shader(source)
        except Exception:  # ruff: ignore[blind-except]
            self._last_mtime = mtime
            return
        if self.compute is not None:
            self.compute.release()
        self.compute = new_compute
        self._last_mtime = mtime
        print(f"[Reloaded] {SHADER_PATH.relative_to(BASE_DIR)}")  # ruff: ignore[print]

    def save_output_png(self) -> None:
        if self.out_tex is None:
            return
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        w, h = self._tex_size
        raw = self.out_tex.read()
        floats = struct.unpack(f"{w * h * 4}f", raw)
        rgba_bytes = bytes(
            max(0, min(255, int(c * 255.0 + 0.5))) for c in floats
        )
        img = Image.frombytes("RGBA", (w, h), rgba_bytes).transpose(
            Image.Transpose.FLIP_TOP_BOTTOM
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # ruff: ignore[call-datetime-now-without-tzinfo]
        out_file = SCREENSHOT_DIR / f"output_seed_{self.seed}_{timestamp}.png"
        img.save(out_file)
        print(f"[Saved Image] {out_file}")  # ruff: ignore[print]

    def on_key_event(self, key, action, modifiers) -> None:  # pyright: ignore[reportMissingParameterType]  # ruff: ignore[missing-type-function-argument, unused-method-argument]
        if action != self.wnd.keys.ACTION_PRESS:
            return
        if key == self.wnd.keys.R:
            self.seed = secrets.randbelow(10**6)
            self._update_title()
            print(f"[Seed] {self.seed}")  # ruff: ignore[print]
        elif key == self.wnd.keys.S:
            self.save_output_png()
        elif key == self.wnd.keys.SPACE:
            self.paused = not self.paused
            self._update_title()

    def on_render(self, time: float, frame_time: float) -> None:  # ruff: ignore[unused-method-argument]
        if not self.paused:
            self.sim_time += frame_time

        self._load_compute_shader()
        self._ensure_target_texture()

        w, h = self._tex_size
        self.out_tex.bind_to_image(0, read=False, write=True)  # pyright: ignore[reportOptionalMemberAccess]

        if self.compute is not None:
            if "u_resolution" in self.compute:
                self.compute["u_resolution"].value = (float(w), float(h))  # pyright: ignore[reportAttributeAccessIssue]
            if "u_time" in self.compute:
                self.compute["u_time"].value = self.sim_time  # pyright: ignore[reportAttributeAccessIssue]
            if "u_seed" in self.compute:
                self.compute["u_seed"].value = int(self.seed)

            self.compute.run(math.ceil(w / 16), math.ceil(h / 16), 1)

        self.ctx.memory_barrier(moderngl.SHADER_IMAGE_ACCESS_BARRIER_BIT)

        self.ctx.clear()
        self.out_tex.use(location=0)  # pyright: ignore[reportOptionalMemberAccess]
        self.vao.render(moderngl.TRIANGLE_STRIP)


if __name__ == "__main__":
    moderngl_window.run_window_config(ComputeSandbox)
