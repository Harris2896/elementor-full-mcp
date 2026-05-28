from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.section import (
    section_add,
    section_delete,
    section_duplicate,
    section_get,
    section_history,
    section_list,
    section_reorder,
    section_restore,
    section_update,
)


def test_section_list():
    client = MagicMock()
    client.get.return_value = ok([])
    section_list(client, page_id=1)
    client.get.assert_called_once_with("/pages/1/sections")


def test_section_get():
    client = MagicMock()
    client.get.return_value = ok({})
    section_get(client, page_id=1, sid="abc")
    client.get.assert_called_once_with("/pages/1/sections/abc")


def test_section_add_with_position():
    client = MagicMock()
    client.post.return_value = ok({"sid": "new"})
    json_blob = {"id": "new", "elType": "section", "settings": {}, "elements": []}
    section_add(client, page_id=1, section_json=json_blob, position=2)
    client.post.assert_called_once_with("/pages/1/sections", json={"json": json_blob, "position": 2})


def test_section_add_omits_position_when_none():
    client = MagicMock()
    client.post.return_value = ok({"sid": "new"})
    section_add(client, page_id=1, section_json={"id": "x"})
    client.post.assert_called_once_with("/pages/1/sections", json={"json": {"id": "x"}})


def test_section_update():
    client = MagicMock()
    client.put.return_value = ok({"sid": "a"})
    section_update(client, page_id=1, sid="a", section_json={"id": "a"})
    client.put.assert_called_once_with("/pages/1/sections/a", json={"json": {"id": "a"}})


def test_section_delete_duplicate_reorder():
    client = MagicMock()
    client.delete.return_value = ok({})
    client.post.return_value = ok({})
    section_delete(client, page_id=1, sid="a")
    section_duplicate(client, page_id=1, sid="a")
    section_reorder(client, page_id=1, order=["b", "a"])
    client.delete.assert_called_with("/pages/1/sections/a")
    assert client.post.call_args_list[0].args == ("/pages/1/sections/a/duplicate",)
    assert client.post.call_args_list[1].args == ("/pages/1/sections/reorder",)
    assert client.post.call_args_list[1].kwargs == {"json": {"order": ["b", "a"]}}


def test_section_history_and_restore():
    client = MagicMock()
    client.get.return_value = ok([])
    client.post.return_value = ok({})
    section_history(client, page_id=1)
    section_restore(client, page_id=1, version=2)
    client.get.assert_called_with("/pages/1/backups")
    client.post.assert_called_with("/pages/1/backups/2/restore", json={})
