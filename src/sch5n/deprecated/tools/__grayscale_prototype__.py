# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy from itertools import product
lazy from typing import cast

lazy from PIL import Image

lazy from sch5n.math.scalar import avg


def _main() -> None:
    # Open the grayscale image
    gray_image = Image.open("gray_image.png")

    # Define the color you want to shade the image with
    shade_color = (
        255,
        127,
        63,
        255,
    )  # Red color, you can change this to any other color
    trans_color = (255, 0, 254, 255)  # Transparent color

    # Convert the grayscale image to RGBA format
    rgba_image = gray_image.convert("RGBA")

    # Create a new RGBA image of the same size as the grayscale image
    shaded_image = Image.new("RGBA", rgba_image.size)

    # Iterate over each pixel of the grayscale image and apply the shade color
    for x, y in product(range(rgba_image.width), range(rgba_image.height)):
        pixel = cast(
            "tuple[int, int, int, int]", rgba_image.getpixel((x, y))
        )  # Returns IntTuple4 because of RGBA mode
        if pixel == trans_color:
            shaded_pixel = (0, 0, 0, 0)
        else:
            if not (pixel[0] == pixel[1] == pixel[2]):
                intensity = int(avg(*pixel[:3]))
            else:
                intensity = pixel[0]

            shaded_pixel = (
                shade_color[0],
                shade_color[1],
                shade_color[2],
                intensity,
            )
        shaded_image.putpixel((x, y), shaded_pixel)

    # Display or save the resulting shaded image
    shaded_image.show()  # Display the shaded image
    shaded_image.save("shaded_image.png")  # Save the shaded image


if __name__ == "__main__":
    _main()
