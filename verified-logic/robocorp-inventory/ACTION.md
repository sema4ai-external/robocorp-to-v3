# Robocorp Inventory

## Purpose
Read-only dump of one Robocorp Control Room workspace into Project files, for step 3 ("Inventory") of the `robocorp-relink` skill.

## Prerequisites (in the calling Project)
- Network allowlist: `cloud.robocorp.com:443`.
- A network credential the person creates in the UI: environment name `ROBOCORP_API`, host `cloud.robocorp.com`, method `GET`, path prefix `/api/v1/workspaces/<workspace id>`, authentication **API key header** named `Authorization`, value `RC-WSKEY <key>`. The code sends the opaque marker from the environment variable; the gateway swaps in the key. The key never appears in code, files or chat.

## Inputs
- `workspace_id` (required): Control Room workspace UUID.
- `output_dir`: default `relink/inventory`.
- `process_ids`: limit details to these processes.
- `refresh`: re-fetch existing files (default false, so a stopped run resumes).
- `max_seconds`: default 100. Control Room allows ~1 request/second, so a big workspace may need several calls; repeat until `complete` is true.
- `credential_env`, `api_base`: defaults `ROBOCORP_API`, `https://cloud.robocorp.com`.

## Output files
- `workspace.json`, `processes.json`, `task-packages.json`, `workers.json`, `worker-groups.json`, `assets.json`, `secrets.json` (names and descriptions only), `webhooks.json`.
- `processes/<id>.json`: full process detail (steps, worker targets, triggers, schedules, notifications).
- `summary.json`: per process: steps with package name, task, worker, parallelism, timeout, env var names (not values), `desktop` (Control Room's "Use Desktop Connection" settings under their v3 `task_package.run` names: `desktop_needed`, `desktop_login_timeout_seconds`, `desktop_no_sign_out_after_run`, `record_video`), triggers, schedule/notification/webhook counts.

## Output
Counts, the process list, `pending_process_ids` and `complete`.

## Side Effects
- GET requests to the Control Room API only. Never calls `/secrets/<name>`.
- Writes JSON files under `output_dir`.

## Not covered
Worker group membership: the Control Room API has no read endpoint for it. Ask the person.
