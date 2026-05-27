import os

import pytest

from elementor_mcp.config import Settings


@pytest.fixture
def live_settings():
    api_key = os.environ.get("EMCP_TEST_API_KEY")
    wp_url  = os.environ.get("EMCP_TEST_WP_URL", "http://localhost:8888")
    if not api_key:
        pytest.skip("EMCP_TEST_API_KEY not set — skipping integration test")
    return Settings(
        wp_url=wp_url,
        wp_api_key=api_key,
        log_level="info",
        http_timeout=10,
    )
