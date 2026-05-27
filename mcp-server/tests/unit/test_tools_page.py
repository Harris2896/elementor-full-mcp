from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.page import page_create, page_delete, page_get, page_list


def test_page_list_passes_no_params_by_default():
    client = MagicMock()
    client.get.return_value = ok([])
    page_list(client)
    client.get.assert_called_once_with("/pages", params=None)


def test_page_list_passes_search_and_per_page():
    client = MagicMock()
    client.get.return_value = ok([])
    page_list(client, search="about", per_page=10)
    client.get.assert_called_once_with("/pages", params={"search": "about", "per_page": 10})


def test_page_create_sends_title_and_profile_id():
    client = MagicMock()
    client.post.return_value = ok({"id": 4})
    page_create(client, title="Landing", profile_id=2)
    client.post.assert_called_once_with("/pages", json={"title": "Landing", "profile_id": 2})


def test_page_create_omits_profile_when_none():
    client = MagicMock()
    client.post.return_value = ok({"id": 5})
    page_create(client, title="X")
    client.post.assert_called_once_with("/pages", json={"title": "X"})


def test_page_get_and_delete():
    client = MagicMock()
    client.get.return_value = ok({"id": 7})
    client.delete.return_value = ok({"deleted": True})
    page_get(client, page_id=7)
    page_delete(client, page_id=7)
    client.get.assert_called_with("/pages/7")
    client.delete.assert_called_with("/pages/7")
