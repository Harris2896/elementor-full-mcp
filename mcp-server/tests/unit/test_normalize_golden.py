import json
from pathlib import Path

from elementor_mcp.core.normalizer.normalize import normalize_section

FIX = Path(__file__).parent.parent / "fixtures"


def test_hero_simple_stacks_western_normalization_matches_golden():
    template = json.loads((FIX / "templates" / "hero-simple.json").read_text(encoding="utf-8"))
    profile = json.loads((FIX / "profiles" / "stacks-western.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (FIX / "expected" / "hero-simple__stacks-western.json").read_text(encoding="utf-8")
    )

    section = template["content"][0]
    result = normalize_section(section, profile)

    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)
