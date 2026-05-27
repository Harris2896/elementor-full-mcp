import pytest

from elementor_mcp.config import Settings


@pytest.fixture
def settings():
    return Settings(
        wp_url="http://localhost:8888",
        wp_api_key="emcp_test_key",
        log_level="info",
        http_timeout=5,
    )
