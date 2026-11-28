# Copyright (c) 2026 Schunche
"""Tests for the light map."""

from __future__ import annotations

import numpy as np
import pytest

from sch5n.client.render.lightmap import (
    MAX_SOURCES,
    light_field,
    night_pixels,
)


def test_no_sources_means_dark() -> None:
    """Without a light the field is zero everywhere."""
    assert not light_field(np.zeros((6, 8), dtype=np.uint8)).any()


def test_light_fades_with_distance() -> None:
    """A source is brightest in its own tile and fades to nothing."""
    radii = np.zeros((21, 21), dtype=np.uint8)
    radii[10, 10] = 7
    field = light_field(radii)
    assert field[10, 10] == pytest.approx(1.0)
    assert field[10, 10] > field[10, 12] > field[10, 16] > 0.0
    assert field[10, 18] == pytest.approx(0.0)
    assert field[10, 12] == pytest.approx(field[12, 10])


def test_lights_combine_by_strongest() -> None:
    """Two sources never light a tile more than fully."""
    radii = np.zeros((5, 9), dtype=np.uint8)
    radii[2, 2] = radii[2, 4] = 3
    assert light_field(radii).max() <= 1.0


def test_sources_near_the_edge_are_clipped() -> None:
    """A light on the border of the region does not fail."""
    radii = np.zeros((4, 4), dtype=np.uint8)
    radii[0, 0] = 9
    assert light_field(radii)[0, 0] == pytest.approx(1.0)


def test_many_sources_are_capped() -> None:
    """A crowd of lights still gives a field."""
    radii = np.full((60, 60), 2, dtype=np.uint8)
    assert len(np.nonzero(radii)[0]) > MAX_SOURCES
    assert light_field(radii).max() > 0.0


def test_light_lifts_the_dark() -> None:
    """Lit pixels are clearer than dark ones, and warmer."""
    light = np.array([[0.0, 1.0]], dtype=np.float32)
    pixels = night_pixels(light, 0.55)
    assert pixels.shape == (1, 2, 4)
    assert pixels[0, 1, 3] < pixels[0, 0, 3] / 4
    assert pixels[0, 1, 0] > pixels[0, 0, 0]
    assert pixels[0, 0, 3] == int(0.55 * 255)
