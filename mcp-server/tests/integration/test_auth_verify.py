from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.auth import auth_verify


def test_health_endpoint_reachable(live_settings):
    client = WpClient(live_settings)
    res = client.get("/health")
    assert res.ok is True, res.error
    assert res.data["status"] == "ok"


def test_auth_verify_returns_user_id(live_settings):
    client = WpClient(live_settings)
    res = auth_verify(client)
    assert res.ok is True, res.error
    assert isinstance(res.data["user_id"], int)
    assert res.data["user_id"] > 0
