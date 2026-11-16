"""Download one Control Room task package zip into Project files."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

try:  # loaded as a package by sdk.verified
    from .rc_client import Client, RobocorpApiError
except ImportError:  # loaded as a plain module
    from rc_client import Client, RobocorpApiError

MAX_BYTES = 12 * 1024 * 1024  # per-file capture limit for Verified Logic writes


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "package"


def run(input: dict[str, object]) -> dict[str, object]:
    workspace_id = str(input["workspace_id"]).strip().lower()
    package_id = str(input["package_id"]).strip()
    if not re.match(r"^[A-Za-z0-9-]{1,64}$", package_id):
        raise ValueError("package_id must be a Control Room task package id")
    out = str(input.get("output_dir") or "relink/packages").strip("/")
    if not out or out.startswith(".") or ".." in out.split("/"):
        raise ValueError("output_dir must be a plain workspace-relative folder")
    client = Client(
        str(input.get("api_base") or "https://cloud.robocorp.com"),
        workspace_id,
        str(input.get("credential_env") or "ROBOCORP_API"),
    )

    detail = client.get(f"/task-packages/{package_id}")
    url = (detail.get("download") or {}).get("url")
    if not url:
        raise RobocorpApiError(f"task package {package_id} has no download URL (type {detail.get('type')})")
    host = urllib.parse.urlsplit(url).hostname or ""

    # The signed URL is used once and never written anywhere. No Authorization header goes to S3.
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as resp:
            data = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise RobocorpApiError(f"package download failed with {e.code}; retry, the signed link may have expired") from None
    except urllib.error.URLError as e:
        raise RobocorpApiError(
            f"Could not reach the package storage host {host} ({e.reason}). Add {host}:443 to the Project's "
            "network allowlist and run again."
        ) from None
    if len(data) > MAX_BYTES:
        raise RobocorpApiError("package is larger than 12 MiB; download it by hand and upload it to the Project")

    base = f"{out}/{_slug(str(detail.get('name') or package_id))}"
    zip_path = f"{base}.zip"
    full = os.path.join("/workspace", zip_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(data)
    try:
        with zipfile.ZipFile(full) as zf:
            files = sorted(n for n in zf.namelist() if not n.endswith("/"))
    except zipfile.BadZipFile:
        os.remove(full)
        raise RobocorpApiError("the download is not a valid zip file") from None

    meta = {
        "id": detail.get("id"),
        "name": detail.get("name"),
        "type": detail.get("type"),
        "tasks": [t.get("name") for t in detail.get("tasks") or []],
        "configuration": detail.get("configuration"),
        "zip_path": zip_path,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    with open(os.path.join("/workspace", f"{base}.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    return {
        **meta,
        "metadata_path": f"{base}.json",
        "storage_host": host,
        "file_count": len(files),
        "has_robot_yaml": any(f == "robot.yaml" or f.endswith("/robot.yaml") for f in files),
        "files": files[:200],
    }
