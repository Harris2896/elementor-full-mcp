import pytest

from elementor_mcp.config import Settings


def test_loads_from_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env in cwd
    monkeypatch.setenv("WP_URL", "http://wp.local")
    monkeypatch.setenv("WP_API_KEY", "emcp_aaaa_bbbb")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("HTTP_TIMEOUT", "30")
    s = Settings()
    assert str(s.wp_url) == "http://wp.local/"
    assert s.wp_api_key == "emcp_aaaa_bbbb"
    assert s.log_level == "debug"
    assert s.http_timeout == 30


def test_missing_required_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WP_URL", raising=False)
    monkeypatch.delenv("WP_API_KEY", raising=False)
    with pytest.raises(ValueError):  # pydantic ValidationError extends ValueError
        Settings(_env_file=None)


def test_optional_api_keys_default_to_empty(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WP_URL", "http://wp.local")
    monkeypatch.setenv("WP_API_KEY", "emcp_x_y")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    from elementor_mcp.config import Settings
    s = Settings()
    assert s.openai_api_key == ""
    assert s.unsplash_access_key == ""


def test_optional_api_keys_load_when_set(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WP_URL", "http://wp.local")
    monkeypatch.setenv("WP_API_KEY", "emcp_x_y")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "us-test")
    from elementor_mcp.config import Settings
    s = Settings()
    assert s.openai_api_key == "sk-test"
    assert s.unsplash_access_key == "us-test"
