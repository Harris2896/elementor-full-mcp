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
