"""Read-only inventory of a Robocorp Control Room workspace into Project files."""

from __future__ import annotations

import json
import os
import time

try:  # loaded as a package by sdk.verified
    from .rc_client import Client
except ImportError:  # loaded as a plain module
    from rc_client import Client

LISTS = ["processes", "task-packages", "workers", "worker-groups", "assets", "secrets", "webhooks"]


def _write(path: str, data: object) -> None:
    full = os.path.join("/workspace", path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def _read(path: str) -> object | None:
    full = os.path.join("/workspace", path)
    if not os.path.isfile(full):
        return None
    with open(full, encoding="utf-8") as fh:
        return json.load(fh)


def _desktop(dc: dict | None) -> dict:
    """Control Room's "Use Desktop Connection" settings for a step, named as v3 task_package.run names them.

    Settings other than `desktop_needed` are only meaningful when it is on; Control Room returns null for them on
    steps that never had a desktop (e.g. cloud workers).
    """
    dc = dc or {}
    enabled = bool(dc.get("enabled"))
    return {
        "desktop_needed": enabled,
        "desktop_login_timeout_seconds": dc.get("login_timeout") if enabled else None,
        "desktop_no_sign_out_after_run": bool(dc.get("do_not_sign_out_after_run")) if enabled else False,
        "record_video": bool(dc.get("video_streaming_enabled")) if enabled else False,
    }


def _summarise(detail: dict, packages: dict[str, str], webhooks: list[dict]) -> dict:
    steps = []
    for s in detail.get("steps") or []:
        tp = s.get("task_package") or {}
        steps.append(
            {
                "name": s.get("name"),
                "package_id": tp.get("id"),
                "package_name": packages.get(str(tp.get("id"))),
                "task": (tp.get("task") or {}).get("name"),
                "worker": s.get("worker"),
                "max_parallel": s.get("maximum_parallel_executions"),
                "timeout_s": s.get("execution_timeout"),
                "env_var_names": sorted(k for k in (s.get("environment_variables") or {}) if k),
                "desktop": _desktop(s.get("desktop_connection")),
            }
        )
    return {
        "id": detail.get("id"),
        "name": detail.get("name"),
        "steps": steps,
        "triggers": [t.get("type") for t in detail.get("triggers") or []],
        "schedules": len(detail.get("schedules") or []),
        "notifications": len(detail.get("notifications") or []),
        "webhooks": sum(1 for w in webhooks if (w.get("process") or {}).get("id") == detail.get("id")),
        "has_default_input": detail.get("default_input") is not None,
    }


def run(input: dict[str, object]) -> dict[str, object]:
    started = time.monotonic()
    workspace_id = str(input["workspace_id"]).strip().lower()
    out = str(input.get("output_dir") or "relink/inventory").strip("/")
    if not out or out.startswith(".") or ".." in out.split("/"):
        raise ValueError("output_dir must be a plain workspace-relative folder")
    max_seconds = float(input.get("max_seconds") or 100)
    only = input.get("process_ids")
    refresh = bool(input.get("refresh", False))
    client = Client(
        str(input.get("api_base") or "https://cloud.robocorp.com"),
        workspace_id,
        str(input.get("credential_env") or "ROBOCORP_API"),
        deadline=started + max_seconds,
    )

    written: list[str] = []
    lists: dict[str, list[dict]] = {}
    if refresh or _read(f"{out}/workspace.json") is None:
        ws = client.get("")
        _write(f"{out}/workspace.json", ws)
        written.append(f"{out}/workspace.json")
    ws = _read(f"{out}/workspace.json") or {}
    cached_id = str(ws.get("id") or "").lower()
    if cached_id != workspace_id:
        raise ValueError(
            f"{out} holds an inventory of Control Room workspace {cached_id or '(unknown)'}, not {workspace_id}. "
            "Use another output_dir, or refresh: true to replace it."
        )

    for name in LISTS:
        path = f"{out}/{name}.json"
        cached = None if refresh else _read(path)
        if cached is None:
            rows = client.list_all(f"/{name}")
            if name == "secrets":
                rows = [{"name": r.get("name"), "description": r.get("description")} for r in rows]
            _write(path, rows)
            written.append(path)
            cached = rows
        lists[name] = cached  # type: ignore[assignment]

    packages = {str(p["id"]): p.get("name") for p in lists["task-packages"]}
    wanted = [p["id"] for p in lists["processes"]]
    if only:
        ids = {str(i) for i in only}  # type: ignore[union-attr]
        unknown = sorted(ids - set(wanted))
        if unknown:
            raise ValueError(f"process_ids not in this workspace: {', '.join(unknown)}")
        wanted = [i for i in wanted if i in ids]

    pending: list[str] = []
    for pid in wanted:
        path = f"{out}/processes/{pid}.json"
        if not refresh and _read(path) is not None:
            continue
        if client.out_of_time():
            pending.append(pid)
            continue
        _write(path, client.get(f"/processes/{pid}"))
        written.append(path)

    summaries = []
    for pid in wanted:
        detail = _read(f"{out}/processes/{pid}.json")
        if isinstance(detail, dict):
            summaries.append(_summarise(detail, packages, lists["webhooks"]))
    summaries.sort(key=lambda s: (s["name"] or "").lower())
    _write(f"{out}/summary.json", {"workspace": ws.get("name"), "processes": summaries})
    written.append(f"{out}/summary.json")

    return {
        "workspace_name": ws.get("name"),
        "organization": (ws.get("organization") or {}).get("name"),
        "output_dir": out,
        "counts": {name: len(rows) for name, rows in lists.items()},
        "processes_detailed": len(summaries),
        "pending_process_ids": pending,
        "complete": not pending,
        "api_calls": client.calls,
        "files_written": len(written),
        "processes": [
            {"id": s["id"], "name": s["name"], "steps": len(s["steps"]), "triggers": s["triggers"], "schedules": s["schedules"]}
            for s in summaries
        ],
    }
