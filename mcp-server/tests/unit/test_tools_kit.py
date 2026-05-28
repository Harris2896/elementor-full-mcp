from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.kit import kit_get, kit_set


def test_kit_get():
    client = MagicMock()
    client.get.return_value = ok({})
    kit_get(client)
    client.get.assert_called_once_with("/kit")


def test_kit_set():
    client = MagicMock()
    client.put.return_value = ok({"kit_post_id": 11})
    kit_set(client, settings={"a": 1})
    client.put.assert_called_once_with("/kit", json={"a": 1})
