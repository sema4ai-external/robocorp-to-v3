# Install guide (for the AI tool)

You are installing the Robocorp relink kit from this repository into the person's Sema4.ai v3 workspace through the **Sema4 Workspace MCP** connector (tools `workspace`, `authoring`, `sandbox`; your tool may prefix them with the connector's name, such as `mcp__sema4__workspace`, and may need to load them first). You also need a local shell for `tar` and `curl`. Follow these steps in order. Tell the person in one line what each step does before you do it. Never ask for or handle any secret. Nothing here needs one.

The kit has to be installed at **org scope**. The skill calls the Verified Logic as `org:robocorp-inventory`, `org:robocorp-fetch-package` and `org:robocorp-code-peek`.

## 1. Check the connection and what's already there

- Call `workspace.context`. If no workspace comes back, stop and tell the person to connect the v3 Workspace MCP first (see README).
- If several workspaces come back, ask which one to install into.
- Note a team you can create projects in. If there's only one, use it without asking.
- Call `workspace.whoami`. If the connection lacks `workspace:publish`, or the person isn't a workspace admin, say so now: the install will need an admin to run it or to approve what it submits.
- Record what is installed now: `authoring.list_verified_logic` with `scope: "org"` (note `slug` and `current_version_id` of the three `robocorp-*` packages, if present) and `authoring.get_skill` with `slug: "robocorp-relink"`, `scope: "org"` (note `version_id`; "not found" is fine). If they exist, tell the person this is an **update**.

To create an `idempotency_key`, generate a UUID: `uuidgen` (macOS/Linux) or `[guid]::NewGuid()` (PowerShell).

## 2. Host project

Drafts are written into an ordinary project before they are published. The published skill and Verified Logic don't depend on it afterwards.

- If a project named **Robocorp Relink Toolkit** is in `workspace.context`, reuse it. Archived projects aren't listed and don't need restoring; just create a new one.
- Otherwise, `workspace.create_project` with `name: "Robocorp Relink Toolkit"`, the team's `team_id`, a fresh UUID as `idempotency_key`, and a description such as "Hosts the drafts of the Robocorp relink skill and Verified Logic."

## 3. Verified Logic

Verified Logic drafts live under `.blockparty/verified-action-drafts/org/<slug>/` in the host project. That folder can only be written from the sandbox, so upload one archive and unpack it there.

1. On the person's machine, from the repository root, pack the three packages. Leave out macOS metadata and caches:

   macOS / Linux:
   ```bash
   COPYFILE_DISABLE=1 tar czf /tmp/relink-verified-logic.tgz --exclude '__pycache__' --exclude '._*' -C verified-logic robocorp-inventory robocorp-fetch-package robocorp-code-peek
   ```

   Windows (PowerShell; `tar.exe` ships with Windows 10 and later):
   ```powershell
   tar.exe -czf "$env:TEMP\relink-verified-logic.tgz" --exclude __pycache__ -C verified-logic robocorp-inventory robocorp-fetch-package robocorp-code-peek
   ```

2. `workspace.request_upload` with `project_id`, `path: "kit/relink-verified-logic.tgz"` and `local_file_path` set to the archive's full path. Run the returned `command`. It carries an upload ticket that only allows writing this one path and expires in 5 minutes. It will appear in your tool's command history, which is fine, but don't repeat it in chat or in your report.

   On Windows the command is bash-style: run it in Git Bash, or in PowerShell call `curl.exe` (not `curl`, which is an alias there) with the same arguments, putting the `--header` value in double quotes and writing the file as `--data-binary "@C:\full\path\relink-verified-logic.tgz"`.

3. `sandbox.run_with_proposal` (python) in the host project:

   ```python
   import os, tarfile
   root = "/workspace/.blockparty/verified-action-drafts/org"
   os.makedirs(root, exist_ok=True)
   with tarfile.open("/workspace/kit/relink-verified-logic.tgz") as t:
       members = [m for m in t.getmembers()
                  if not os.path.basename(m.name).startswith("._") and "__pycache__" not in m.name]
       t.extractall(root, members=members)
   os.remove("/workspace/kit/relink-verified-logic.tgz")
   for d, _, fs in sorted(os.walk(root)):
       for f in sorted(fs):
           print(os.path.join(d, f)[len("/workspace/"):])
   ```

   Expect 14 files: `ACTION.md`, `action.py`, `action.yaml` and `examples/basic.json` in each package, plus `rc_client.py` in inventory and fetch-package. The proposal lists 15 paths: those 14 and the removal of the uploaded archive.

4. `workspace.apply_run` with the returned `run_id` and `proposal_review_id`, accepting all paths. A Verified Logic package is accepted all or nothing.

5. Check: `authoring.list_verified_logic` with `scope: "org"` must list `robocorp-inventory`, `robocorp-fetch-package` and `robocorp-code-peek`, each with a `current_version_id` different from what you recorded in step 1 (or new). Applying an org draft publishes it directly when the person may publish. The listing includes full schemas and is large; read only slug, `current_version_id` and `updated_at`.
   - If any is missing or older, call `authoring.list_authoring_requests` with `kind: "verified_logic"` and `pending_only: true`. Pending requests need approval: tell the person to have a workspace admin approve them in v3, then check again.
   - Don't use `authoring.submit_verified_logic` here; it looks for a project-scope draft.

## 4. Skill

1. `authoring.open_skill_draft` with the host `project_id`, `slug: "robocorp-relink"`, `scope: "org"`. It returns `draft_root` (`.blockparty/skill-drafts/org/robocorp-relink`). An `existing_skill_id` just means this is an update.
2. `workspace.request_upload` with `path: "<draft_root>/SKILL.md"` and `local_file_path` set to `skills/robocorp-relink/SKILL.md` in this repository. Run the returned `command`.
3. `authoring.publish_skill` with the host `project_id`, `slug: "robocorp-relink"`, `scope: "org"`.
   - `outcome: "published"` with `candidate_report.state: "valid"` means done.
   - `proposed` or `awaiting_approval_from` means a workspace admin must approve the proposal in v3. Tell the person.
   - Any `diagnostics`: show them and stop. `transformations` such as `document_reserialized` are expected and fine.

## 5. Smoke test (no Control Room access needed)

`sandbox.run` (python) in the host project. It builds a tiny package in the sandbox and peeks at it; nothing is saved:

```python
import json, zipfile, sdk
z = "/workspace/kit-smoke.zip"
with zipfile.ZipFile(z, "w") as f:
    f.writestr("robot.yaml", "tasks:\n  Demo:\n    shell: python -m robocorp.tasks run tasks.py\n")
    f.writestr("tasks.py", "from robocorp import storage, vault, workitems\n"
               "def demo():\n    vault.get_secret('demo_login')['password']\n"
               "    storage.get_text('demo_prices')\n    workitems.inputs.current.get_file('orders.xlsx')\n")
r = sdk.verified.run("org:robocorp-code-peek", {"zip_path": "kit-smoke.zip"})
ok = ([s["name"] for s in r["secrets"]] == ["demo_login"] and [a["name"] for a in r["assets_read"]] == ["demo_prices"]
      and r["uses_work_item_files"])
print("code-peek:", "OK" if ok else json.dumps(r, indent=1))
refs = set()
for a in sdk.verified.list_approved():
    refs.add(a.get("ref") if isinstance(a, dict) else getattr(a, "ref", None))
for slug in ("robocorp-inventory", "robocorp-fetch-package", "robocorp-code-peek"):
    print(slug, "available" if f"org:{slug}" in refs else f"MISSING (refs seen: {sorted(r for r in refs if r and 'robocorp' in r)})")
```

Every line must say `OK` or `available`. Then `authoring.search_skills` with `query: "relink Robocorp Control Room processes"` must return `robocorp-relink` at scope `org`.

Don't run `robocorp-inventory` or `robocorp-fetch-package` here. They need a Control Room key in a relink project, which the skill sets up later.

Finally, delete the local archive (`/tmp/relink-verified-logic.tgz` or `%TEMP%\relink-verified-logic.tgz`).

## 6. Report

Tell the person, briefly:
- what was published (skill and three Verified Logic, with their scope and new version ids), whether it was a new install or an update, and anything waiting for approval;
- the host project name, and that it can stay as it is;
- how to start: in a v3 project chat, or here with the v3 connector, say **"Relink my Robocorp Control Room processes to v3."**

## If something fails

- **Permission refused** (publishing, org scope): the person needs a workspace admin to run the install, or to approve the requests.
- **Upload command fails:** the ticket expires after 5 minutes. Request a new one and run it right away. A cloud-hosted agent may not reach a private v3 host from its own machine; run the install from a tool on a network that reaches v3.
- **`apply_run` rejects a package:** show the reason. A Verified Logic package is accepted only whole, so check that all of its files were unpacked.
