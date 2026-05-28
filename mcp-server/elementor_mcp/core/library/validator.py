from typing import Any

_TOP_LEVEL = {"content", "page_settings", "version", "title", "type"}


def validate_template(data: Any) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["template must be a JSON object"], "warnings": []}

    content = data.get("content")
    if not isinstance(content, list):
        errors.append("missing or invalid 'content' (must be array of sections)")
    else:
        for i, section in enumerate(content):
            if not isinstance(section, dict):
                errors.append(f"content[{i}] is not an object")
                continue
            if not section.get("id"):
                errors.append(f"content[{i}] missing 'id'")
            if not section.get("elType"):
                errors.append(f"content[{i}] missing 'elType'")
            if not isinstance(section.get("elements", []), list):
                errors.append(f"content[{i}].elements must be an array")

    for k in data:
        if k not in _TOP_LEVEL:
            warnings.append(f"unknown top-level key: '{k}'")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}
