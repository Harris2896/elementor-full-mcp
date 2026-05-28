import base64

from ..config import Settings
from ..core.image.media_upload import upload_image_to_wp
from ..core.image.openai_gen import generate_image_openai
from ..core.image.slot import detect_image_slots
from ..core.image.unsplash_fallback import generate_image_unsplash
from ..core.wp_client import WpClient
from ..envelope import ToolResult, fail, ok
from ..errors import ErrorCode


def image_generate(
    *,
    settings: Settings,
    prompt: str,
    width: int,
    height: int,
    prefer: str = "openai",
) -> ToolResult:
    """Generate an image at exact dimensions. Try preferred provider first, fall back to the other."""
    providers = ["openai", "unsplash"] if prefer == "openai" else ["unsplash", "openai"]
    last_err = None
    for src in providers:
        if src == "openai":
            result = generate_image_openai(
                prompt=prompt, width=width, height=height, api_key=settings.openai_api_key,
            )
        else:
            result = generate_image_unsplash(
                query=prompt, width=width, height=height, access_key=settings.unsplash_access_key,
            )
        if result.ok:
            data = dict(result.data)
            data["bytes_b64"] = base64.b64encode(data.pop("bytes")).decode("ascii")
            data["source"] = src
            return ok(data)
        last_err = result.error

    msg = last_err.message if last_err else "both providers failed"
    return fail(ErrorCode.E_IMAGE_GEN_FAILED, msg)


def image_upload(
    *,
    client: WpClient,
    content_b64: str,
    filename: str,
    mime: str = "image/png",
) -> ToolResult:
    """Upload a base64-encoded image to the WP Media Library."""
    try:
        content = base64.b64decode(content_b64)
    except Exception as e:
        return fail(ErrorCode.E_INVALID_JSON, f"invalid base64 content: {e}")
    return upload_image_to_wp(client, content=content, filename=filename, mime=mime)


def image_describe_slot(*, section_json: dict) -> ToolResult:
    """Return image-bearing slots in a section JSON."""
    slots = detect_image_slots(section_json)
    return ok({"slots": slots, "count": len(slots)})
