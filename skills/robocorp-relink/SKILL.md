---
name: Robocorp Relink
description: Relink Robocorp Control Room processes into this v3 workspace without rewriting the robots. Starts with a roadmap, sets up a relink Project with networking and a user-entered Robocorp credential, inventories Control Room, lets the person pick processes, reads the task package code for the secrets, assets and software they depend on, has the person map workers, brings over only what the code uses, builds workflows with triggers switched off, and test-runs them.
audience: both
when_to_use:
  - Use this when someone wants to move, migrate or relink Robocorp or Control Room processes to Sema4.ai v3.
  - Use this when someone asks what a Robocorp process depends on (secrets, assets, workers, work item files) before bringing it to v3.
  - Use this to continue or check an ongoing relink that has a relink/log.md in the Project.
icon:
  kind: registry
  registry_key: package
---

# Robocorp relink

A **relink** moves Robocorp Control Room processes into Sema4.ai v3 without rewriting the robots: the same task packages run on v3 workers inside v3 workflows. You drive it through the Sema4 Workspace MCP (`workspace`, `work`, `sandbox`, `task_engine`, `authoring`, `feedback`) and the person does the steps only they can do.

Read the builtin `task-engine` skill (`authoring.get_skill slug=task-engine scope=builtin`) once before the first `task_engine` call.

## Verified Logic this skill uses

All Control Room reading goes through workspace-wide Verified Logic, called from the relink Project's sandbox with `sdk.verified.run(ref, input)`. Don't hand-write Control Room API calls for these jobs; the logic already handles auth, the rate limit, pagination and never touching secret values.

| Ref | Step | Does |
|---|---|---|
| `org:robocorp-inventory` | 3 | Reads processes (steps, workers, triggers, schedules), packages, workers, groups, asset names, Vault secret **names**, webhooks into `relink/inventory/`; writes `summary.json`. Resumable: call again until `complete` is true. |
| `org:robocorp-fetch-package` | 5, 7 | Downloads one task package zip to `relink/packages/<name>.zip` (+ `.json` with tasks and sha256). |
| `org:robocorp-code-peek` | 5 | Reads a package zip without running it: secrets, assets, dynamic (runtime-chosen) names, env and `RC_*` variables, work item use, browser/desktop needs, dependency warnings. |

`sdk.verified.run` runs in the caller's sandbox (max 120 s per sandbox call), so its files land in the Project only from `sandbox.run_with_proposal` + `workspace.apply_run`; a plain `sandbox.run` discards them. Read each package's `ACTION.md` (`sdk.verified.list_approved()`) if an input is unclear.

## Where this runs

- **Workspace MCP client** (for example Claude Code connected to this workspace): every operation named here exists (`workspace`, `work`, `sandbox`, `task_engine`, `authoring`, `feedback`).
- **In-product Project agent**: call the Verified Logic above with `sdk.verified.run`; use the equivalent tools you have for the rest. If a `task_engine` operation (adding packages, creating secrets or assets, worker groups) isn't available to you, don't work around it: give the person the exact UI steps (name, content type, item names) and verify afterwards by name.

## Start here: show the roadmap

**Before any question or tool call, show the person this roadmap**, so they know what's coming, what's theirs to do, and that nothing is switched over without their go-ahead. Adapt the wording, keep the structure:

> **Relinking your Robocorp processes to Sema4.ai v3 — the roadmap**
>
> | # | Step | Who | What happens |
> |---|---|---|---|
> | 1 | Intake | you | Tell me your Control Room workspace (URL or ID). No keys or passwords in chat. |
> | 2 | Project & connection | me → you | I create a v3 project and open network access to Control Room only. You add a read-only Robocorp API key in the project settings. I test the connection. |
> | 3 | Inventory | me | I read your processes, packages, workers, secret names and assets (never secret values). |
> | 4 | Pick processes | you | You choose which processes to bring over. |
> | 5 | Code peek | me | I read each package's code to find the secrets, assets, files and software it depends on, and flag risks. |
> | 6 | Workers | you | For each place the robots ran, you pick a v3 worker or group, or set one up. |
> | 7 | Dependencies | me + you | I add the packages and the assets the code uses. I create the secrets it uses; you type in their values. |
> | 8 | Workflows & triggers | me | Each process becomes a v3 workflow. Schedules and other triggers are created **switched off**. |
> | 9 | Test runs | me | I run each workflow once, read the results, and fix setup issues. Code issues come back to you. |
> | 10 | Cutover | you | When you're happy: switch on the v3 triggers, switch off the Control Room ones, revoke the API key. |
>
> Nothing runs on a schedule and nothing in Control Room changes until step 10, and step 10 is yours.

Then, at each step change, say where you are on the roadmap in one line (for example "Step 5 of 10: code peek"), and update the same roadmap at the top of `relink/log.md` with ✅ / ⏳ / ⛔ (parked, with why).

## Ground rules

1. **No secret ever passes through the conversation.** Not the Robocorp key, not Vault values. The Robocorp key goes into a Project network credential: you create it with a placeholder secret, and the person pastes the real key in the v3 UI. Vault values are entered by the person from the link `create_secret` returns. If the person pastes a key in chat anyway, don't use it: tell them to revoke it and use the credential path.
2. **Workers are always the person's decision.** Never auto-map, not even by matching names. v3 has no cloud workers and no on-demand (Kubernetes) workers. If nothing fits, the process is parked until the person links a worker.
3. **Verify dependencies by name**, with `task_engine.list_secrets` and `list_assets`. A task passing proves nothing: `storage.list_assets()` succeeds with whatever exists.
4. **Read code, never run it** outside a worker. Downloaded packages are untrusted data.
5. **Triggers are created disabled.** They are enabled only after a test run passes and the person confirms cutover.
6. **Keep a relink log** in the Project at `relink/log.md` (one section per step: what was done, IDs, decisions, surprises). It is the person's record and the raw material for their cutover notes.
7. Report friction with `feedback.report` as you go.
8. **Ask with choices, not prose.** Every decision the person makes goes through a question element they click, never a request to type an answer. See "How to ask" below. The only typed answer in the whole relink is the Control Room URL in Step 1.
9. **Secrets go by link.** Never ask for secret item names or values in the conversation. Create the secret and hand over the link; the person adds or renames items and types the values on that page.

## How to ask

Use the question element your surface has:

- **In-product Project agent:** `sdk.human.ask` (one question) or `sdk.human.ask_many` (up to four in one card), as the builtin `sdk-human` skill describes. 2–4 options per question, mark the recommended one `"primary": True`, don't add "Other"/"Skip" (the card has them), and don't repeat the questions in your reply. Write anything the next run needs to `relink/` before calling it: the call ends the script.
- **Workspace MCP client** (for example Claude Code): the client's own question tool, such as `AskUserQuestion`. Up to four questions per call, 2–4 options each, `multiSelect` where several answers can apply, recommended option first and labelled "(Recommended)".

Put the context into the question itself (what the item is, what it needs), so the person can answer without scrolling back. When there are more candidates than options fit (processes, assets), offer the sensible groups as options (recommended set, all, none) and name the individual items in the prompt or descriptions; the person can still write a different answer.

| Step | Question | Options |
|---|---|---|
| 2 | Is the key pasted into the credential? | "Pasted, test it" / "Help me create the key" |
| 4 | Which processes to bring over? | recommended starter set / processes with schedules or email triggers / all N; multi-select per process when the tool allows and N ≤ 4 |
| 5 | Which assets does `<process>` use (dynamic access)? | the asset names (multi-select), or "All N" / "None" / a named subset |
| 6 | Where should all targets run? (shortcut) | "All on <group>" per group, "All on <worker>" per worker, "Choose per target" |
| 6 | Then, only on "Choose per target", one question per distinct Robocorp target | each v3 group, each v3 worker, "None fits — I'll set one up" |
| 7 | Bring over exactly these dependencies? | "Yes, create them" / "Change the list" |
| 7 | Have you entered the secret values? | "Done, test it" / "Later, test the rest" |
| 9 | A test failed on package code: what next? | "I'll fix the package" / "Park this process" |

## Step 1 — Intake (chat)

Ask for non-secret facts only:
- The Control Room workspace URL (e.g. `https://cloud.robocorp.com/<org>/<workspace>` or a regional host). You need the **workspace ID**: it's in Control Room → Workspace settings, or in the URL of most pages. A workspace key can't discover its own workspace, and a wrong ID returns `WORKSPACE_DOESNT_MATCH_KEY`.
- The API host for that workspace (`cloud.robocorp.com` unless they're on a regional/dedicated instance; check the URL).
- Which v3 team owns the work (`workspace.context` lists teams; pick the only one without asking).

## Step 2 — Project and connection

1. `workspace.create_project` in that team, named `Robocorp relink – <workspace name>`. Tell the person its link.
2. Explain that you're opening outbound network access, then `workspace.replace_project_network_policy` with mode `host_port_allowlist` and destination `<api host>:443`. Check `network_availability` in `get_project_settings` first; if the gateway or rollout is off, stop and say an admin must enable Project networking. Package downloads need one more host (the S3 bucket behind Control Room's signed links, e.g. `eu1-….s3.eu-west-1.amazonaws.com`); `robocorp-fetch-package` names it exactly the first time it's blocked, and you add it then (step 5).
3. **Create the credential yourself with a placeholder secret**, so the person only has to paste the key. `workspace.create_project_network_credential` (fresh UUID `idempotency_key`):

   ```json
   {"displayName": "Robocorp WS",
    "environmentName": "ROBOCORP_API",
    "rules": [{"hostname": "<api host>",
               "pathPrefix": "/api/v1/workspaces/<workspace id>",
               "allowedMethods": ["GET"],
               "authentication": {"kind": "header", "name": "Authorization"}}]}
   ```

   with `secret_value` = `RC-WSKEY placeholder-replace-me`. The placeholder is not a secret. Never put anything the person gave you into `secret_value`. If a credential with that environment name already exists, don't create a second one. Reuse it, and check its rules with `get_project_network_credential`.

   Then ask the person to create a **dedicated read-only workspace API key** in Control Room (Workspace settings → API keys; read access to processes, task packages, workers, worker groups, assets, Vault listing, webhooks). Have them replace the placeholder in v3: give the **Project link** and the path **Project settings → Network → Credentials → Robocorp WS → edit**. The credential API returns no link of its own. They change only the secret field, to `RC-WSKEY ` followed by the key (one space after `RC-WSKEY`; it is the whole Authorization value). Everything else is already filled in.

   If creating the credential fails (no admin rights on the Project, API refused), fall back to having the person add it in **Credentials → Add** with these form values, filled in with the actual IDs:

   | Field | Value |
   |---|---|
   | **Credential name** | `Robocorp WS` |
   | **Environment variable** | `ROBOCORP_API` (exactly; the Verified Logic reads this name) |
   | **HTTPS hostname** | `<api host>` (e.g. `cloud.robocorp.com`) |
   | **Path prefix** | `/api/v1/workspaces/<workspace id>` |
   | **Allowed methods** | tick `GET` only |
   | **Authentication format** | **API key header (Gemini, Anthropic)** |
   | **Credential field name** | `Authorization` |
   | the secret itself | `RC-WSKEY ` followed by the key |

   The key never reaches chat, files or code: the sandbox only sees an opaque marker in `ROBOCORP_API` and the network gateway swaps in the real value. Ask "Is the key pasted in?" as a question element ("Pasted, test it" / "Help me create the key"). `secretConfigured` is already true for the placeholder, so it tells you nothing here. The Step 4 test is the only proof: a 401 means the placeholder is still in place, or the key is wrong.
4. Test the connection by starting Step 3: the first thing `robocorp-inventory` does is read the workspace. Success = the workspace name comes back. Its errors say what to fix: 401/403 → placeholder not replaced yet, wrong key, or missing `RC-WSKEY ` prefix; `WORKSPACE_DOESNT_MATCH_KEY` → wrong workspace ID; "could not reach" → allowlist; "ROBOCORP_API is not set" → credential missing or a different environment name.

## Step 3 — Inventory

In `sandbox.run_with_proposal` (timeout 120):
```python
import sdk
r = sdk.verified.run("org:robocorp-inventory", {"workspace_id": WS, "max_seconds": 100})
print(r["workspace_name"], r["counts"], r["complete"], r["pending_process_ids"])
```
then `workspace.apply_run` to keep the files. If `complete` is false, run the same call again (existing files are skipped) until it is. About 1 request per second: ~60 s for 50 processes.

Write `relink/inventory.md` from `relink/inventory/summary.json` and the list files:

- Totals: processes, steps, packages (used vs orphaned), workers, groups, cloud worker types, secrets, assets, webhooks, triggers (email, schedule, API).
- Per process: steps (package, task, worker target, env var names, parallelism, timeout, desktop connection on/off), triggers, schedules (keep the timezone exactly, from `processes/<id>.json`), notifications.
- Packages shared by several processes: relink each package once.
- Orphaned packages: not in scope unless asked.

Known API quirks:
- Cloud workers aren't in `/workers`; steps reference them by a container-type ID.
- **Secret item keys can't be read through the API.** The only Vault read, `GET /secrets`, returns `name` and `description`; no endpoint returns a secret's items, not even their keys. Keys come from the code (Step 5) or from the person on the v3 secret page (Step 7).
- There is **no API to read group membership** (`/worker-groups/{id}/workers` doesn't exist; only add/remove, which are writes). Get it from the person.
- Package type `zip` is what `robocorp-fetch-package` downloads. `public_git` / `github` packages need the repository instead.

## Step 4 — Pick processes (person)

Show the process list (name, trigger kinds, step count, worker kinds, last-used if known), then ask which to bring over with a question element (see "How to ask"). Make the recommended option a starter set of one or two simple processes that still cover what matters (secrets, assets, work items, schedules), and name them in its description. Record the choice in the log.

## Step 5 — Code peek (per selected package)

For each package used by the selected processes (`package_id` from `summary.json`), in one `sandbox.run_with_proposal`:
```python
f = sdk.verified.run("org:robocorp-fetch-package", {"workspace_id": WS, "package_id": PKG})
peek = sdk.verified.run("org:robocorp-code-peek", {"zip_path": f["zip_path"]})
```
then `workspace.apply_run` (the zips are needed again in Step 7). If the fetch says the storage host is blocked, add exactly that host to the allowlist, tell the person, and retry.

`robocorp-code-peek` gives the dependency tree: `secrets`, `assets_read` / `assets_written`, `dynamic_access`, `env_vars`, `rc_vars_used`, `uses_work_items` / `uses_work_item_files`, `ui_requirements`, `dependencies` and `warnings`, each with `file:line`. It is pattern-based, so open the files it points to (unzip in the sandbox, read, never execute) to:
- collect each secret's **item keys** (`secret["username"]`, `${secret}[password]`). If the code reads the whole secret (`secret.items()`, a loop, passing the dict on), the keys can't be read from the code: don't ask for them, the person adds them on the secret page in Step 7,
- resolve `dynamic_access` where you can (from the step's env vars or config); otherwise ask the person with a question element listing the workspace's asset (or secret) names,
- confirm anything listed under `warnings`.

What the findings mean:

| Look for | Means |
|---|---|
| `vault.get_secret("x")`, `Get Secret  x` (`RPA.Robocorp.Vault`) | Vault secret `x`; collect the **item keys** read from it (`["username"]`, `${secret}[password]`) |
| `storage.get_text/get_json/get_file/set_*("x")`, `RPA.Robocorp.Storage` keywords | Asset `x` |
| `storage.list_assets()`, asset names built at runtime (variables, f-strings, config) | **dynamic access**: the name can't be read from the code. Don't bring every asset. Ask with a question element which of the workspace's assets this automation actually uses |
| `vault.get_secret(<variable>)` or a secret name from config/env | dynamic secret name: resolve it from the step's env vars or config if you can, otherwise ask with a question element listing the Vault secret names |
| `robocorp.workitems`, `RPA.Robocorp.WorkItems`, `Get Work Item File  <name>` | work item contract; note exact attachment file names |
| producer creates output items, consumer reads them | producer → consumer: becomes `items: {from_step: <producer key>}` |
| `RC_*` / `ROBOCORP_*` env reads | run context; see the v3 caveats below |
| step env vars vs. what the code reads | dead config is common; keep it but note it |
| hardcoded credentials | flag, don't fix |
| Selenium/Playwright, `RPA.Windows`, `RPA.Desktop`, SAP | worker needs a browser / desktop / specific software |
| `conda.yaml` with old `rpaframework` and only top-level pins | **environment drift risk**: a fresh build on a new worker can pull incompatible transitive deps (seen: `webdriver-manager` ≥3.9 breaks `rpaframework` 17.x). Flag it; the fix (pin) is the person's in the SDK |

`RC_*` on v3 workers: set — `RC_WORKSPACE_ID` (v3 workspace), `RC_RUNTIME_ID` (worker id), `RC_WORKITEM_ID`, `RC_ACTIVITY_RUN_ID`, `RC_PROCESS_RUN_ID`, `RC_PROCESS_ID`, API hosts/tokens. **`RC_PROCESS_ID` and `RC_PROCESS_RUN_ID` both equal the worker run id.** Not set: `RC_ACTIVITY_ID`, `RC_ACTIVITY_NAME`, `RC_ACTIVITY_RUN_NUMBER`, `RC_PROCESS_NAME`, `RC_PROCESS_RUN_NUMBER`, `RC_ELEMENT_ID`, `RC_ENVIRONMENT_NAME`. Flag code that depends on the missing ones or on a stable process id.

Write the findings per process into `relink/inventory.md` and show the person a short summary.

## Step 6 — Workers (person)

Read `task_engine.list_workers` and `list_worker_groups` (with members). Worker mapping is **always** asked with question elements: never show a mapping table and ask the person to type an answer such as "all → X".

First, one shortcut question: "Where should all <n> Robocorp targets run?" Its prompt lists each target with what it needs. Options: "All on <group>" for each v3 group (recommended when one fits), "All on <worker>" for each v3 worker, and "Choose per target". When the person picks "All on …", that's the whole mapping. Skip this question when there is only one target.

On "Choose per target", ask **one question per distinct** Robocorp target across the selected processes (self-hosted worker, worker group, cloud worker type), all in one card (`ask_many` / one `AskUserQuestion` call; more than four targets → several cards). Each question's prompt carries:
- what it was (cloud worker → Linux container, probably had a browser; self-hosted → name; group → name, members unknown from the API) and which steps use it,
- what it needs (browser, Windows desktop, software from Step 5); a step with Control Room's "Use Desktop Connection" on needs a Windows worker that can open a Remote Desktop session,
- parallelism > 1 → the v3 group needs that many online workers to actually run in parallel.

Options: each v3 group (`workers.group_id`, recommended when one fits, since machines can be added later), each v3 worker (`workers.worker_id`), and **"None fits — I'll set one up"**. Show online/offline and OS in each option's description.

"None fits" parks the processes using that target. Tell the person how: v3 → Workers → Connect a worker (Windows: Setup Utility with a link token; macOS/Linux: link command), install what the robot needs, then you can create a group and add the worker (`create_worker_group`, `add_worker_to_group`, admin). Re-read the lists before continuing.

## Step 7 — Bring the dependencies over

**Scope rule:** bring over only the secrets and assets the selected automations refer to: names found in the code in Step 5, plus the ones the person picked for dynamic access. Never copy a whole Vault or asset store, and don't bring along anything that "might be used". Show the exact set and confirm it with a question element ("Yes, create them" / "Change the list") before creating anything.

**Packages** (builder): the zip is already in `relink/packages/` from Step 5; `task_engine.add_package(name, path)` with that path. A name that already exists gets a new **version** — check `list_packages` first and pick a fresh name rather than overwriting an unrelated package. Note the `package_id` and task names. (rcc also works: `rcc cloud new` + `rcc cloud push` against `https://<v3 host>/api/v1/rc/rcc/`.)

**Vault secrets** (admin): check `list_secrets`. For each referenced secret that's missing, `task_engine.create_secret(name, description, item_names)` right away — don't ask the person anything first:
- `item_names`: the item keys found in Step 5. When the code reads the whole secret and no key is known, use one placeholder item `value`.
- `description`: where it came from (the Control Room secret name and description) and which task reads it.
- Then hand over the returned link as a clickable markdown link, one per secret, with: the Control Room secret to copy from (Control Room → Vault → `<name>`), the items to fill in, and, when the keys were unknown, "add the same item names it has in Control Room and remove `value`". Values and item names are typed only on that page.
- Then ask "Have you entered the secret values?" as a question element ("Done, test it" / "Later, test the rest") and carry on with the other steps while they do it; only test runs that read the secret wait for it.

Names: letters, digits, underscore. If the Robocorp name doesn't fit, stop and tell the person the code has to change.

**Assets** (admin): check `list_assets`. For each referenced asset that's missing, fetch its content in the sandbox (`GET /assets/{id}` with header `Authorization: os.environ["ROBOCORP_API"]` → `payload.url`, then download that link without the header; throttle ~1 req/s), save as a Project file with `run_with_proposal` + `apply_run`, then `set_asset(name, path, content_type)` with the exact Robocorp name and content type. Asset values aren't secrets, but don't echo their contents into chat. If an asset with that name already exists, ask before replacing.

Re-check `list_secrets` / `list_assets` against the dependency list. Nothing proceeds to test with a name missing.

## Step 8a — Workflows

One workflow per process (`work.create_workflow`, kind `workflow_v2`), one `task_package.run` step per Robocorp step:

| Robocorp | v3 |
|---|---|
| step | `task_package.run` with `package_id`, `task`, `label` (the step name), `key` (short slug) |
| worker target | `workers.worker_id` or `workers.group_id` from Step 6 |
| `maximum_parallel_executions` | `workers.max_parallel` (needs a group) |
| step env vars | `variables`. Names must match `[A-Za-z0-9_]`, `RC_` prefix reserved. Drop empty names. A hyphenated name the code reads = code change needed |
| `execution_timeout` (s) | `timeout_minutes` = s/60, **max 1440** |
| "Use Desktop Connection" (summary `desktop`) | copy the four fields as they are: `desktop_needed`, and only when it's true `desktop_login_timeout_seconds` (omit when null; 0 = no limit), `desktop_no_sign_out_after_run`, `record_video`. See "Desktop settings" below |
| items passed from the previous step | `items: {from_step: <previous key>}` |
| first step input | the Work Item payload, with attachments as the item's files (file names preserved) |
| description | say what to attach (e.g. "attach the orders workbook named exactly orders.xlsx") |

Validate first (`validate_workflow`), then create.

**Desktop settings.** This works whether or not this v3 has per-step desktop settings:
- **Supported** (the `task_package.run` step in the `work` authoring schema lists `desktop_needed`): copy the settings as in the table. Without them v3 opens a Remote Desktop session for every run, and most Control Room steps have the desktop connection off: on a Windows worker each session needs a Remote Desktop license. Leave `record_video` and `desktop_no_sign_out_after_run` out of steps without a desktop (rejected without `desktop_needed: true`); `desktop_no_sign_out_after_run` also needs Workforce Agent Core 6.23 or later on the worker.
- **Not supported** (no `desktop_needed` in the schema, or `validate_workflow` rejects a `desktop_*` field as extra/not permitted): leave out the three `desktop_*` fields and validate again. `record_video` already exists there: set it for steps that had video streaming on. Every run then gets a desktop session, as before. Note in the log which steps had the desktop connection off in Control Room, and tell the person once that those can be switched to `desktop_needed: false` when v3 supports it.
- The settings come from `summary.json` (`desktop`); an inventory written by an older version has no `desktop`, so read `desktop_connection` from `processes/<id>.json` (`enabled`, `login_timeout`, `do_not_sign_out_after_run`, `video_streaming_enabled`).
- A step with the desktop connection off whose code uses `RPA.Windows`, `RPA.Desktop` or other UI automation (Step 5) is worth a word to the person: it may have relied on a console session already open on the machine.

## Step 8b — Triggers (all `enabled: false`)

- **Schedule** → `schedule` trigger, `config: {inputs: {}}`. Weekdays Mon=0 … Sun=6, same time, same IANA timezone. Cron schedules: translate if it's a weekly/daily/monthly pattern, otherwise ask. `start_with_input_items` has no equivalent (a schedule submits a new Work Item) — tell the person.
- **Email** → `hosted_email` (new address) or `email_mailbox` (from `list_trigger_sources`). Hosted email fails with "Hosted email is not configured for this installation" until an admin sets the mail domain — check early and tell the person. Either way **the address changes**: ask who sends to the old one.
- **API-started** → `webhook` trigger.
- **Notifications**: Slack can be an `agent.prompt` step using `sdk.notify` (bot invited to the channel) or a `human.request` notify target. Outbound run-event webhooks have no equivalent; tell the person.

## Step 9 — Test runs

1. `list_workers`: the target must be online.
2. Upload any test attachment (`request_upload`, use the package's `devdata/` sample if there is one) and `submit_work_item` with `attachment_paths`.
3. Follow with `get_work_item wait_seconds=30`; one online worker means steps from different workflows queue.
4. On failure: `task_engine.get_task_run` (per-item failure messages) → `get_task_run_console` (the traceback is above rcc's timeline; the tail only shows the exit code). Classify: **setup** (secret items, asset value, variables, items, worker software) → fix it yourself; **package code or environment** → explain and hand to the person for the SDK, then rerun after they add the new version.
5. Never read the console of a task that prints secrets.

Record results in the log.

## Step 10 — Cutover (person decides)

Checklist to hand over:
- [ ] Test runs pass; compare with a recent Control Room run of the same process.
- [ ] Enable the v3 triggers (`replace_workflow_trigger enabled: true`).
- [ ] Disable the schedules / email triggers of the same processes in Control Room so nothing runs twice.
- [ ] Tell email senders the new address.
- [ ] Revoke the Robocorp API key in Control Room and delete the Project network credential; set the network policy back to `disabled` if nothing else needs it.

## Done means

`relink/inventory.md` and `relink/log.md` are complete, each selected process is a v3 workflow with disabled triggers and a recorded test result, every dependency exists by name, and the person has the cutover checklist with what's left for them.
