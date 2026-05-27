import httpx
import respx

from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.errors import ErrorCode


@respx.mock
def test_get_returns_envelope_on_success(settings):
    respx.get("http://localhost:8888/wp-json/elementor-mcp/v1/health").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "data": {"status": "ok"}, "warnings": [], "error": None},
        )
    )
    client = WpClient(settings)
    res = client.get("/health")
    assert res.ok is True
    assert res.data == {"status": "ok"}


@respx.mock
def test_get_sends_bearer_header(settings):
    route = respx.get("http://localhost:8888/wp-json/elementor-mcp/v1/auth/verify").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "data": {"user_id": 1}, "warnings": [], "error": None},
        )
    )
    WpClient(settings).get("/auth/verify")
    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer emcp_test_key"


@respx.mock
def test_get_returns_fail_envelope_on_401(settings):
    respx.get("http://localhost:8888/wp-json/elementor-mcp/v1/auth/verify").mock(
        return_value=httpx.Response(
            401,
            json={"code": "emcp_auth_invalid", "message": "Invalid API key"},
        )
    )
    res = WpClient(settings).get("/auth/verify")
    assert res.ok is False
    assert res.error.code == ErrorCode.E_WP_AUTH.value


@respx.mock
def test_get_returns_fail_envelope_on_connection_error(settings):
    respx.get("http://localhost:8888/wp-json/elementor-mcp/v1/health").mock(
        side_effect=httpx.ConnectError("refused")
    )
    res = WpClient(settings).get("/health")
    assert res.ok is False
    assert res.error.code == ErrorCode.E_WP_UNREACHABLE.value
