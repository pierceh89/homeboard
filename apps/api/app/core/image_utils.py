from io import BytesIO

from fastapi import HTTPException


def convert_png_to_8bit_grayscale(image_bytes: bytes) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="Pillow is not installed") from exc

    with Image.open(BytesIO(image_bytes)) as image:
        output = BytesIO()
        # Kindle endpoint returns an 8-bit grayscale PNG to reduce output depth.
        image.convert("L").save(output, format="PNG")
        return output.getvalue()
