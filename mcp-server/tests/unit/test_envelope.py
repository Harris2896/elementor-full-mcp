from elementor_mcp.envelope import ToolResult, fail, ok
from elementor_mcp.errors import ErrorCode


def test_ok_envelope_shape():
    r = ok({"x": 1}, warnings=["w"])
    assert r.ok is True
    assert r.data == {"x": 1}
    assert r.warnings == ["w"]
    assert r.error is None
    d = r.model_dump()
    assert d == {"ok": True, "data": {"x": 1}, "warnings": ["w"], "error": None}


def test_fail_envelope_shape():
    r = fail(ErrorCode.E_NO_PROFILE, "no profile yet", fix_hint="create one")
    assert r.ok is False
    assert r.data is None
    assert r.error is not None
    assert r.error.code == "E_NO_PROFILE"
    assert r.error.fix_hint == "create one"


def test_parse_envelope_from_dict():
    r = ToolResult.model_validate({
        "ok": True, "data": {"hello": "world"}, "warnings": [], "error": None
    })
    assert r.data == {"hello": "world"}


def test_error_codes_have_strings():
    assert ErrorCode.E_WP_AUTH.value == "E_WP_AUTH"
    assert ErrorCode.E_WP_UNREACHABLE.value == "E_WP_UNREACHABLE"
