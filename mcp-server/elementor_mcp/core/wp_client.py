from typing import Any

import httpx

from ..config import Settings
from ..envelope import ToolResult, fail, ok
from ..errors import ErrorCode

NAMESPACE = "/wp-json/elementor-mcp/v1"


class WpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base = str(settings.wp_url).rstrip("/")
        self._http = httpx.Client(
            timeout=settings.http_timeout,
            headers={"Authorization": f"Bearer {settings.wp_api_key}"},
        )

    def _url(self, path: str) -> str:
        return f"{self.base}{NAMESPACE}{path}"

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> ToolResult:
        return self._request("GET", path, params=params)

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> ToolResult:
        return self._request("POST", path, json=json)

    def put(self, path: str, *, json: dict[str, Any] | None = None) -> ToolResult:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> ToolResult:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str, **kw: Any) -> ToolResult:
        url = self._url(path)
        try:
            resp = self._http.request(method, url, **kw)
        except httpx.ConnectError as e:
            return fail(ErrorCode.E_WP_UNREACHABLE, f"Cannot reach WP at {url}: {e}")
        except httpx.HTTPError as e:
            return fail(ErrorCode.E_INTERNAL, f"HTTP error: {e}")

        if resp.status_code == 401:
            return fail(ErrorCode.E_WP_AUTH, "WP rejected API key")
        if resp.status_code >= 500:
            return fail(ErrorCode.E_INTERNAL, f"WP returned {resp.status_code}")
        try:
            body = resp.json()
        except ValueError:
            return fail(ErrorCode.E_INTERNAL, "Non-JSON response from WP")

        # Plugin always returns an envelope shape; if it doesn't, wrap it.
        if isinstance(body, dict) and "ok" in body:
            return ToolResult.model_validate(body)
        if resp.status_code >= 400:
            return fail(ErrorCode.E_INTERNAL, f"WP error {resp.status_code}: {body}")
        return ok(body)

    def close(self) -> None:
        self._http.close()
