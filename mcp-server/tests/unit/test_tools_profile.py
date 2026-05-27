from unittest.mock import MagicMock

from elementor_mcp.envelope import fail, ok
from elementor_mcp.errors import ErrorCode
from elementor_mcp.tools.profile import (
    profile_apply,
    profile_create,
    profile_delete,
    profile_get,
    profile_list,
    profile_update,
)


def test_profile_list_delegates():
    client = MagicMock()
    client.get.return_value = ok([{"id": 1, "name": "A"}])
    res = profile_list(client)
    client.get.assert_called_once_with("/profiles")
    assert res.ok is True


def test_profile_get_uses_path_param():
    client = MagicMock()
    client.get.return_value = ok({"id": 7, "name": "X", "data": {}})
    res = profile_get(client, profile_id=7)
    client.get.assert_called_once_with("/profiles/7")
    assert res.data["id"] == 7


def test_profile_create_posts_payload():
    client = MagicMock()
    client.post.return_value = ok({"id": 42})
    payload = {"name": "X", "colors": {}}
    res = profile_create(client, profile=payload)
    client.post.assert_called_once_with("/profiles", json=payload)
    assert res.data["id"] == 42


def test_profile_update_puts_payload():
    client = MagicMock()
    client.put.return_value = ok({"id": 5})
    res = profile_update(client, profile_id=5, profile={"name": "Y", "colors": {}})
    client.put.assert_called_once_with("/profiles/5", json={"name": "Y", "colors": {}})
    assert res.ok is True


def test_profile_delete_calls_delete():
    client = MagicMock()
    client.delete.return_value = ok({"id": 6, "deleted": True})
    res = profile_delete(client, profile_id=6)
    client.delete.assert_called_once_with("/profiles/6")
    assert res.ok is True


def test_profile_apply_posts_empty_body():
    client = MagicMock()
    client.post.return_value = ok({"kit_post_id": 99, "profile_id": 5})
    res = profile_apply(client, profile_id=5)
    client.post.assert_called_once_with("/profiles/5/apply", json={})
    assert res.data["kit_post_id"] == 99


def test_profile_get_propagates_404():
    client = MagicMock()
    client.get.return_value = fail(ErrorCode.E_INTERNAL, "Profile 99 not found")
    res = profile_get(client, profile_id=99)
    assert res.ok is False
