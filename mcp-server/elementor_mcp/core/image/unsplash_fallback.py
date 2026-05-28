from io import BytesIO

import httpx
from PIL import Image

from ...envelope import ToolResult, fail, ok
from ...errors import ErrorCode

_SEARCH_URL = "https://api.unsplash.com/search/photos"


def generate_image_unsplash(
    *, query: str, width: int, height: int, access_key: str, timeout: int = 15,
) -> ToolResult:
    if not access_key:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, "no unsplash access key configured")

    try:
        resp = httpx.get(
            _SEARCH_URL,
            params={"query": query, "per_page": 1, "orientation": _orientation(width, height)},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"unsplash search failed: {e}")

    results = body.get("results") or []
    if not results:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"no unsplash result for query: {query}")

    raw_url = results[0].get("urls", {}).get("raw") or results[0].get("urls", {}).get("regular")
    if not raw_url:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, "unsplash result missing image URL")

    try:
        img_resp = httpx.get(raw_url, timeout=timeout)
        img_resp.raise_for_status()
        img = Image.open(BytesIO(img_resp.content)).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        png_bytes = out.getvalue()
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"unsplash image fetch failed: {e}")

    return ok({"bytes": png_bytes, "mime": "image/png", "width": width, "height": height})


def _orientation(w: int, h: int) -> str:
    if w >= h * 1.2:
        return "landscape"
    if h >= w * 1.2:
        return "portrait"
    return "squarish"
