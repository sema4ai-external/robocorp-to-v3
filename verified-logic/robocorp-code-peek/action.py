"""Static dependency scan of a Robocorp task package zip.

Reads the code; never runs it. Finds the Vault secrets, Storage assets,
environment variables, work item use, UI needs and dependency pins that a
relink to v3 has to account for.
"""

from __future__ import annotations

import os
import re
import zipfile

CODE_EXT = (".py", ".robot", ".resource")
MAX_FILE_BYTES = 2_000_000

# RC_* variables Control Room sets that v3 workers do not (observed 2026-11-13).
RC_NOT_SET_ON_V3 = {
    "RC_ACTIVITY_ID",
    "RC_ACTIVITY_NAME",
    "RC_ACTIVITY_RUN_NUMBER",
    "RC_PROCESS_NAME",
    "RC_PROCESS_RUN_NUMBER",
    "RC_ELEMENT_ID",
    "RC_ENVIRONMENT_NAME",
}
# Set on v3, but with a different meaning than in Control Room.
RC_DIFFERENT_ON_V3 = {
    "RC_PROCESS_ID": "equals the worker run id on v3, not a stable process id",
    "RC_PROCESS_RUN_ID": "equals the worker run id on v3",
    "RC_RUNTIME_ID": "is the v3 worker id",
}

STR = r"""(?:'([^'\n]+)'|"([^"\n]+)")"""

PY_SECRET = re.compile(r"\bget_secret\s*\(\s*" + STR)
PY_SECRET_ANY = re.compile(r"\bget_secret\s*\(")
PY_SECRET_SET = re.compile(r"\bset_secret\s*\(")
# Storage methods share names with other libraries (work items' `get_file`, Selenium's `get_text`), so a call
# counts as an asset access only on a Storage receiver, or bare when the file imports it from robocorp.storage.
PY_ASSET_READ_FNS = r"(?:get_text|get_json|get_file|get_bytes|get_asset|get_text_asset|get_json_asset|get_file_asset)"
PY_ASSET_WRITE_FNS = r"(?:set_text|set_json|set_file|set_bytes|set_text_asset|set_json_asset|set_file_asset|delete_asset)"
PY_STORAGE_RECEIVERS = (r"storage", r"robocorp\.storage", r"Storage\(\)")
PY_STORAGE_ALIAS = re.compile(
    r"^\s*(?:import\s+robocorp\.storage\s+as\s+(\w+)"
    r"|from\s+robocorp\s+import\s+[^\n]*?\bstorage\s+as\s+(\w+)"
    r"|(\w+)\s*=\s*(?:\w+\.)*Storage\s*\(\s*\))",
    re.M,
)
PY_STORAGE_BARE_IMPORT = re.compile(r"^\s*from\s+robocorp\.storage\s+import\b", re.M)
PY_ASSET_LIST = re.compile(r"\blist_assets\s*\(")
PY_CONST = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*str\s*)?=\s*" + STR + r"\s*(?:#.*)?$", re.M)
PY_SECRET_IDENT = re.compile(r"\bget_secret\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,)]")
RC_LITERAL = re.compile(r"""['"](RC_[A-Z0-9_]+)['"]""")
PY_ENV = re.compile(r"""\bos\.(?:environ\.get|getenv)\s*\(\s*""" + STR + r"|\bos\.environ\s*\[\s*" + STR + r"\s*\]")

RF_SECRET = re.compile(r"^\s*(?:\$\{[^}]+\}\s*=?\s+)?Get Secret(?:\s{2,}|\t)+(\S[^\n]*?)\s*$", re.I | re.M)
RF_ASSET_READ = re.compile(
    r"^\s*(?:\$\{[^}]+\}\s*=?\s+)?Get (?:Text|JSON|File) Asset(?:\s{2,}|\t)+(\S[^\n]*?)\s*$", re.I | re.M
)
RF_ASSET_WRITE = re.compile(r"^\s*(?:Set (?:Text|JSON|File) Asset|Delete Asset)(?:\s{2,}|\t)+(\S[^\n]*?)(?:\s{2,}|\t|$)", re.I | re.M)
RF_ASSET_LIST = re.compile(r"^\s*(?:\$\{[^}]+\}\s*=?\s+)?List Assets\b", re.I | re.M)
RF_ENV = re.compile(r"%\{([A-Za-z_][A-Za-z0-9_]*)")
RF_ENV_KW = re.compile(r"Get Environment Variable(?:\s{2,}|\t)+([A-Za-z_][A-Za-z0-9_]*)", re.I)

WORKITEM_MARKERS = ("robocorp.workitems", "RPA.Robocorp.WorkItems", "workitems.inputs", "workitems.outputs")
WORKITEM_FILE_MARKERS = ("get_file(", "Get Work Item File", "Get Work Item Files", "download_files", "Download files")
UI_MARKERS = {
    "browser_selenium": ("RPA.Browser.Selenium",),
    "browser_playwright": ("RPA.Browser.Playwright", "robocorp.browser", "robocorp import browser", "playwright"),
    "desktop": ("RPA.Desktop", "RPA.Windows", "robocorp.windows", "pywinauto", "RPA.Desktop.Windows"),
    "excel_app": ("RPA.Excel.Application", "RPA.Word.Application", "RPA.Outlook.Application"),
    "sap": ("RPA.SAP",),
}
VAULT_MARKERS = ("RPA.Robocorp.Vault", "robocorp.vault", "robocorp import vault")
STORAGE_MARKERS = ("RPA.Robocorp.Storage", "robocorp.storage", "robocorp import storage")


def _storage_call(text: str, fns: str) -> str:
    """Pattern for a Storage method call in this file, up to and including its opening parenthesis."""
    receivers = list(PY_STORAGE_RECEIVERS)
    receivers += [re.escape(next(g for g in m.groups() if g)) for m in PY_STORAGE_ALIAS.finditer(text)]
    qualified = r"\b(?:" + "|".join(receivers) + r")\s*\.\s*"
    prefix = f"(?:{qualified}|(?<![\\w.]))" if PY_STORAGE_BARE_IMPORT.search(text) else qualified
    return prefix + fns + r"\s*\("


def _s(m: re.Match) -> str:
    return next(g for g in m.groups() if g)


def _s_from(m: re.Match, start: int) -> str:
    return next(g for g in m.groups()[start - 1:] if g)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _is_literal_rf(arg: str) -> bool:
    return "${" not in arg and "%{" not in arg and "@{" not in arg and "&{" not in arg


def _parse_conda(text: str) -> list[str]:
    deps: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        m = re.match(r"^\s*-\s+([^\s:][^:]*?)\s*$", line)
        if m and not m.group(1).startswith(("pip", "conda-forge", "defaults")):
            deps.append(m.group(1).strip().strip("'\""))
    return deps


def _parse_robot_yaml(text: str) -> dict:
    tasks: list[str] = []
    env_file = None
    in_tasks = False
    for raw in text.splitlines():
        if re.match(r"^tasks\s*:", raw):
            in_tasks = True
            continue
        if in_tasks:
            m = re.match(r"^  (\S[^:]*):\s*$", raw)
            if m:
                tasks.append(m.group(1).strip().strip("'\""))
                continue
            if raw and not raw.startswith(" "):
                in_tasks = False
        m = re.match(r"^condaConfigFile\s*:\s*(\S+)", raw)
        if m:
            env_file = m.group(1).strip("'\"")
        m = re.match(r"^environmentConfigs\s*:", raw)
        if m and env_file is None:
            env_file = "environmentConfigs"
    return {"tasks": tasks, "environment_file": env_file}


def _add(bucket: dict, name: str, where: str) -> None:
    bucket.setdefault(name, [])
    if where not in bucket[name] and len(bucket[name]) < 10:
        bucket[name].append(where)


def run(input: dict[str, object]) -> dict[str, object]:
    zip_path = input.get("zip_path")
    if not isinstance(zip_path, str) or not zip_path.strip():
        raise ValueError("zip_path must be a workspace-relative path to a task package .zip")
    if zip_path.startswith("/") or ".." in zip_path.split("/"):
        raise ValueError("zip_path must be workspace-relative without '..'")
    full = os.path.join("/workspace", zip_path)
    if not os.path.isfile(full):
        raise FileNotFoundError(f"no such file in the Project: {zip_path}")

    secrets: dict = {}
    assets_read: dict = {}
    assets_written: dict = {}
    env_vars: dict = {}
    dynamic: list[dict] = []
    ui: dict = {}
    uses_vault = uses_storage = uses_workitems = uses_workitem_files = False
    robot_yaml: dict = {"tasks": [], "environment_file": None}
    conda_files: dict[str, list[str]] = {}
    scanned: list[str] = []
    skipped: list[str] = []

    with zipfile.ZipFile(full) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        # A package zip may have one top-level folder; find robot.yaml's root.
        roots = sorted((n[: -len("robot.yaml")] for n in names if n.endswith("robot.yaml")), key=len)
        root = roots[0] if roots else ""
        for name in names:
            rel = name[len(root):] if name.startswith(root) else name
            if rel.startswith(("devdata/", "output/", ".git/", "node_modules/")) or "/__pycache__/" in rel:
                continue
            info = zf.getinfo(name)
            is_code = rel.endswith(CODE_EXT)
            is_env = rel == "robot.yaml" or rel.endswith(("conda.yaml", "package.yaml"))
            if not (is_code or is_env):
                continue
            if info.file_size > MAX_FILE_BYTES:
                skipped.append(rel)
                continue
            text = zf.read(name).decode("utf-8", errors="replace")
            scanned.append(rel)
            if rel == "robot.yaml":
                robot_yaml = _parse_robot_yaml(text)
                continue
            if is_env:
                conda_files[rel] = _parse_conda(text)
                continue

            if any(m in text for m in VAULT_MARKERS):
                uses_vault = True
            if any(m in text for m in STORAGE_MARKERS):
                uses_storage = True
            if any(m in text for m in WORKITEM_MARKERS):
                uses_workitems = True
                if any(m in text for m in WORKITEM_FILE_MARKERS):
                    uses_workitem_files = True
            for key, markers in UI_MARKERS.items():
                if any(m in text for m in markers):
                    _add(ui, key, rel)

            if rel.endswith(".py"):
                consts = {m.group(1): _s_from(m, 2) for m in PY_CONST.finditer(text)}
                asset_read_any = re.compile(_storage_call(text, PY_ASSET_READ_FNS))
                asset_read = re.compile(asset_read_any.pattern + r"\s*" + STR)
                asset_ident = re.compile(asset_read_any.pattern + r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,)]")
                asset_write = re.compile(_storage_call(text, PY_ASSET_WRITE_FNS) + r"\s*" + STR)
                for m in RC_LITERAL.finditer(text):
                    _add(env_vars, m.group(1), f"{rel}:{_line(text, m.start())}")
                resolved_pos = set()
                for m in PY_SECRET_IDENT.finditer(text):
                    if m.group(1) in consts:
                        resolved_pos.add(m.start())
                        _add(secrets, consts[m.group(1)], f"{rel}:{_line(text, m.start())} (via {m.group(1)})")
                for m in asset_ident.finditer(text):
                    if m.group(1) in consts:
                        resolved_pos.add(m.start())
                        _add(assets_read, consts[m.group(1)], f"{rel}:{_line(text, m.start())} (via {m.group(1)})")
                lit_secret_pos = set(resolved_pos)
                for m in PY_SECRET.finditer(text):
                    lit_secret_pos.add(m.start())
                    _add(secrets, _s(m), f"{rel}:{_line(text, m.start())}")
                for m in PY_SECRET_ANY.finditer(text):
                    if m.start() not in lit_secret_pos:
                        dynamic.append({"kind": "secret_name_at_runtime", "where": f"{rel}:{_line(text, m.start())}"})
                for m in PY_SECRET_SET.finditer(text):
                    dynamic.append({"kind": "secret_written", "where": f"{rel}:{_line(text, m.start())}"})
                lit_asset_pos = set(resolved_pos)
                for m in asset_read.finditer(text):
                    lit_asset_pos.add(m.start())
                    _add(assets_read, _s(m), f"{rel}:{_line(text, m.start())}")
                for m in asset_read_any.finditer(text):
                    first = re.match(r"\s*(['\"]|[A-Za-z_][A-Za-z0-9_]*)", text[m.end(): m.end() + 120])
                    arg = first.group(1) if first else ""
                    if arg not in ("'", '"') and arg not in consts:
                        dynamic.append({"kind": "asset_name_at_runtime", "where": f"{rel}:{_line(text, m.start())}"})
                for m in asset_write.finditer(text):
                    _add(assets_written, _s(m), f"{rel}:{_line(text, m.start())}")
                for m in PY_ASSET_LIST.finditer(text):
                    dynamic.append({"kind": "lists_all_assets", "where": f"{rel}:{_line(text, m.start())}"})
                for m in PY_ENV.finditer(text):
                    _add(env_vars, _s(m), f"{rel}:{_line(text, m.start())}")
            else:
                for m in RF_SECRET.finditer(text):
                    arg = re.split(r"\s{2,}|\t", m.group(1))[0]
                    where = f"{rel}:{_line(text, m.start())}"
                    if _is_literal_rf(arg):
                        _add(secrets, arg, where)
                    else:
                        dynamic.append({"kind": "secret_name_at_runtime", "where": where, "expression": arg})
                for m in RF_ASSET_READ.finditer(text):
                    arg = re.split(r"\s{2,}|\t", m.group(1))[0]
                    where = f"{rel}:{_line(text, m.start())}"
                    if _is_literal_rf(arg):
                        _add(assets_read, arg, where)
                    else:
                        dynamic.append({"kind": "asset_name_at_runtime", "where": where, "expression": arg})
                for m in RF_ASSET_WRITE.finditer(text):
                    _add(assets_written, m.group(1).strip(), f"{rel}:{_line(text, m.start())}")
                for m in RF_ASSET_LIST.finditer(text):
                    dynamic.append({"kind": "lists_all_assets", "where": f"{rel}:{_line(text, m.start())}"})
                for rx in (RF_ENV, RF_ENV_KW):
                    for m in rx.finditer(text):
                        _add(env_vars, m.group(1), f"{rel}:{_line(text, m.start())}")

    rc_used = sorted(v for v in env_vars if v.startswith("RC_"))
    warnings: list[str] = []
    all_deps = [d for deps in conda_files.values() for d in deps]
    dep_names = {re.split(r"[=<>!~ \[]", d, 1)[0].lower(): d for d in all_deps}
    unpinned = sorted(d for d in all_deps if not re.search(r"[=<>~]", d) and d.lower() not in ("pip",))
    if unpinned:
        warnings.append("Unpinned dependencies resolve to the newest version on a fresh v3 build: " + ", ".join(unpinned))
    if "browser_selenium" in ui and "webdriver-manager" not in dep_names:
        warnings.append(
            "Uses RPA.Browser.Selenium but does not pin webdriver-manager. A fresh build can pull an incompatible "
            "webdriver-manager (seen: rpaframework 17.7.0 + webdriver-manager 3.9.1 fails to import). Pin it or "
            "upgrade rpaframework before relinking."
        )
    if not conda_files:
        warnings.append("No conda.yaml/package.yaml found; the worker environment cannot be rebuilt as-is.")
    for v in rc_used:
        if v in RC_NOT_SET_ON_V3:
            warnings.append(f"Reads {v}, which v3 workers do not set.")
        elif v in RC_DIFFERENT_ON_V3:
            warnings.append(f"Reads {v}, which {RC_DIFFERENT_ON_V3[v]}.")
    if dynamic:
        warnings.append(
            "Some secrets or assets are chosen at runtime (see dynamic_access). Ask the person which ones are "
            "needed; do not copy everything."
        )
    if uses_vault and not secrets and not any(d["kind"].startswith("secret") for d in dynamic):
        warnings.append("Imports the Vault library but no get_secret call was recognised; read the code by hand.")
    if uses_storage and not (assets_read or assets_written) and not any("asset" in d["kind"] for d in dynamic):
        warnings.append("Imports the Storage library but no asset call was recognised; read the code by hand.")

    return {
        "zip_path": zip_path,
        "tasks": robot_yaml["tasks"],
        "secrets": [{"name": k, "where": v} for k, v in sorted(secrets.items())],
        "assets_read": [{"name": k, "where": v} for k, v in sorted(assets_read.items())],
        "assets_written": [{"name": k, "where": v} for k, v in sorted(assets_written.items())],
        "dynamic_access": dynamic[:50],
        "env_vars": [{"name": k, "where": v} for k, v in sorted(env_vars.items())],
        "rc_vars_used": rc_used,
        "uses_work_items": uses_workitems,
        "uses_work_item_files": uses_workitem_files,
        "ui_requirements": sorted(ui),
        "dependencies": {k: v for k, v in sorted(conda_files.items())},
        "warnings": warnings,
        "files_scanned": sorted(scanned),
        "files_skipped_too_large": skipped,
    }
