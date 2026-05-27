from unittest.mock import MagicMock

from elementor_mcp.envelope import ToolResult, fail, ok
from elementor_mcp.errors import ErrorCode
from elementor_mcp.tools.auth import auth_verify


def test_auth_verify_delegates_to_wp_client():
    client = MagicMock()
    client.get.return_value = ok({"user_id": 7, "caps": ["edit_posts"], "scopes": ["read"]})
    result: ToolResult = auth_verify(client)
    client.get.assert_called_once_with("/auth/verify")
    assert result.ok is True
    assert result.data["user_id"] == 7


def test_auth_verify_propagates_failure():
    client = MagicMock()
    client.get.return_value = fail(ErrorCode.E_WP_AUTH, "Invalid API key")
    result = auth_verify(client)
    assert result.ok is False
    assert result.error.code == "E_WP_AUTH"
