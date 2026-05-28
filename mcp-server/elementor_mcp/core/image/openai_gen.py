import base64
from io import BytesIO

from openai import OpenAI
from PIL import Image

from ...envelope import ToolResult, fail, ok
from ...errors import ErrorCode

# OpenAI gpt-image-1 supports a limited set of sizes. We always request a
# safe one and resize down/up to the slot's exact dimensions with Pillow.
_OPENAI_SIZES = ["1024x1024", "1792x1024", "1024x1792"]


def _pick_openai_size(w: int, h: int) -> str:
    if w >= h * 1.4:
        return "1792x1024"
    if h >= w * 1.4:
        return "1024x1792"
    return "1024x1024"


def generate_image_openai(
    *, prompt: str, width: int, height: int, api_key: str, model: str = "gpt-image-1",
) -> ToolResult:
    if not api_key:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, "no openai api key configured")

    client = OpenAI(api_key=api_key)
    try:
        resp = client.images.generate(
            model=model,
            prompt=prompt,
            size=_pick_openai_size(width, height),
            n=1,
        )
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"openai images.generate failed: {e}")

    try:
        b64 = resp.data[0].b64_json
        raw = base64.b64decode(b64)
        img = Image.open(BytesIO(raw)).convert("RGB")
        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        png_bytes = out.getvalue()
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"image decode/resize failed: {e}")

    return ok({"bytes": png_bytes, "mime": "image/png", "width": width, "height": height})
