"""Minimal read-only Control Room API client for Verified Logic.

Authentication comes from a Project network credential: the credential's
environment variable holds an opaque marker that the egress gateway replaces
with the real `RC-WSKEY <key>` header value. The key never enters code,
files or output. Control Room allows 10 requests per 10 seconds, so every
call is spaced and `too_many_requests` is retried.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SPACING_S = 1.05  # gap between requests; Control Room allows 10 requests per 10 seconds
REQUEST_TIMEOUT_S = 30
RATE_LIMIT_ATTEMPTS = 6  # requests per call, including retries after too_many_requests
RATE_LIMIT_BACKOFF_BASE_S = 3  # wait before the first retry
RATE_LIMIT_BACKOFF_STEP_S = 2  # added to the wait for each further retry


class RobocorpApiError(RuntimeError):
    pass


class Client:
    def __init__(self, api_base: str, workspace_id: str, credential_env: str, deadline: float | None = None):
        if not UUID.match(workspace_id):
            raise ValueError("workspace_id must be a Control Room workspace UUID")
        if not re.match(r"^https://[A-Za-z0-9.-]+$", api_base.rstrip("/")):
            raise ValueError("api_base must look like https://cloud.robocorp.com")
        marker = os.environ.get(credential_env)
        if not marker:
            raise RobocorpApiError(
                f"Environment variable {credential_env} is not set. Add a Project network credential with that "
                "environment name: host cloud.robocorp.com, method GET, path prefix "
                f"/api/v1/workspaces/{workspace_id}, authentication 'API key header' named Authorization, "
                "value 'RC-WSKEY <key>'."
            )
        self.base = f"{api_base.rstrip('/')}/api/v1/workspaces/{workspace_id}"
        self._headers = {"Authorization": marker, "Accept": "application/json"}
        self._last = 0.0
        self.calls = 0
        self.deadline = deadline

    def out_of_time(self, reserve: float = 3.0) -> bool:
        return self.deadline is not None and time.monotonic() + reserve > self.deadline

    def get(self, path_or_url: str) -> dict:
        url = path_or_url if path_or_url.startswith("https://") else self.base + path_or_url
        if not url.startswith(self.base):
            raise RobocorpApiError("refusing a URL outside the configured workspace")
        if "/secrets/" in url:
            raise RobocorpApiError("secret values are never requested")
        for attempt in range(RATE_LIMIT_ATTEMPTS):
            wait = self._last + SPACING_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.calls += 1
            req = urllib.request.Request(url, headers=self._headers)
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                body = e.read()[:500].decode("utf-8", "replace")
                if e.code == 429 or "too_many_requests" in body:
                    time.sleep(RATE_LIMIT_BACKOFF_BASE_S + RATE_LIMIT_BACKOFF_STEP_S * attempt)
                    continue
                if e.code in (401, 403):
                    raise RobocorpApiError(
                        f"Control Room refused the key ({e.code}): {body}. Check that the network credential's "
                        "value is 'RC-WSKEY <key>' with header name Authorization, that its path prefix covers "
                        "this workspace, and that the key has read access."
                    ) from None
                raise RobocorpApiError(f"GET {url[len(self.base):] or '/'} failed with {e.code}: {body}") from None
            except urllib.error.URLError as e:
                raise RobocorpApiError(
                    f"Could not reach Control Room ({e.reason}). Is cloud.robocorp.com:443 in the Project's "
                    "network allowlist?"
                ) from None
        raise RobocorpApiError(f"rate limited repeatedly on {url[len(self.base):]}")

    def list_all(self, path: str, max_pages: int = 50) -> list[dict]:
        rows: list[dict] = []
        page = self.get(path)
        for _ in range(max_pages):
            rows.extend(page.get("data", []))
            nxt = page.get("next")
            if not page.get("has_more") or not nxt:
                return rows
            page = self.get(nxt)
        raise RobocorpApiError(f"{path} has more than {max_pages} pages")
