def merge_diffs(*parts: dict) -> dict:
    """Merge per-pass diff dicts. Lists concatenated; ints summed."""
    out: dict = {}
    for part in parts:
        for k, v in part.items():
            if k in out:
                if (isinstance(v, list) and isinstance(out[k], list)) or (
                    isinstance(v, int) and isinstance(out[k], int)
                ):
                    out[k] = out[k] + v
                else:
                    out[k] = v
            else:
                out[k] = v
    return out
