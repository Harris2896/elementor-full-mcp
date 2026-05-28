import copy
import re

from .color_distance import delta_e

_COLOR_KEY_RE = re.compile(r"(_color$|^background_color$|_text_color$)")

DELTA_SNAP = 5.0
DELTA_ASK = 15.0


def _profile_color_map(profile: dict) -> dict[str, str]:
    """Map each named profile color slot → hex."""
    colors = profile.get("colors") or {}
    out = {}
    for slot in ("primary", "secondary", "text", "accent", "background"):
        if isinstance(colors.get(slot), str):
            out[slot] = colors[slot].upper()
    for item in (colors.get("custom") or []):
        name = item.get("name")
        val = item.get("value")
        if name and isinstance(val, str):
            out[name] = val.upper()
    return out


def _classify(hex_color: str, palette: dict[str, str]) -> tuple[str, str | None, float]:
    """Returns (verdict, slot_id, delta_e). verdict ∈ {snap, warn, overflow}."""
    best_slot = None
    best_delta = float("inf")
    for slot, palette_hex in palette.items():
        d = delta_e(hex_color, palette_hex)
        if d < best_delta:
            best_delta = d
            best_slot = slot
    if best_delta < DELTA_SNAP:
        return ("snap", best_slot, best_delta)
    if best_delta < DELTA_ASK:
        return ("warn", best_slot, best_delta)
    return ("overflow", None, best_delta)


def pass1_colors(section: dict, profile: dict) -> tuple[dict, dict]:
    """Walk the section, snap colors to profile globals, return (new_section, diff)."""
    out = copy.deepcopy(section)
    palette = _profile_color_map(profile)
    diff = {
        "colors_remapped": [],
        "colors_warned":   [],
        "colors_overflow": [],
    }

    def visit_settings(settings: dict) -> None:
        if not isinstance(settings, dict):
            return
        for key in list(settings.keys()):
            if not _COLOR_KEY_RE.search(key):
                continue
            value = settings[key]
            if not isinstance(value, str) or not value.startswith("#"):
                continue
            verdict, slot, d = _classify(value.upper(), palette)
            if verdict == "snap":
                globals_dict = settings.setdefault("__globals__", {})
                globals_dict[key] = f"globals/colors?id={slot}"
                del settings[key]
                diff["colors_remapped"].append({
                    "key": key, "from": value.upper(), "to": slot, "delta_e": round(d, 2),
                })
            elif verdict == "warn":
                diff["colors_warned"].append({
                    "key": key, "from": value.upper(), "nearest": slot, "delta_e": round(d, 2),
                })
            else:
                if value.upper() not in [c["hex"] for c in diff["colors_overflow"]]:
                    diff["colors_overflow"].append({"key": key, "hex": value.upper()})

    def visit(node: dict) -> None:
        visit_settings(node.get("settings"))
        for child in node.get("elements", []) or []:
            visit(child)

    visit(out)
    return out, diff
