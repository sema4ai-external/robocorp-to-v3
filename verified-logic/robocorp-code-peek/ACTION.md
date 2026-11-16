# Robocorp Code Peek

## Purpose
Static scan of one Robocorp task package zip. It reads `.py`, `.robot` and `.resource` files plus `robot.yaml` and `conda.yaml`. It never runs the code.

## When To Use
- Step 5 ("Code peek") of the `robocorp-relink` skill, after `robocorp-fetch-package`.
- Whenever you need to know which Vault secrets and Storage assets a package reads, so only those get created on v3.

## Inputs
- `zip_path`: workspace-relative path of the package zip, for example `relink/packages/web-store-orders.zip`.

## Output
- `tasks`: task names from `robot.yaml`.
- `secrets`, `assets_read`, `assets_written`: names used literally (or through a module-level string constant) with `file:line`.
- `dynamic_access`: places where the secret or asset name is decided at runtime (`get_secret(var)`, `list_assets()`, `Get Secret  ${name}`). Ask the person which ones are needed; never copy everything.
- `env_vars`, `rc_vars_used`: environment variables read, and Control Room `RC_*` variables referenced.
- `uses_work_items`, `uses_work_item_files`, `ui_requirements` (browser_selenium, browser_playwright, desktop, excel_app, sap): worker needs.
- `dependencies`: entries per conda/package yaml.
- `warnings`: relink risks: RC_* variables v3 does not set or sets differently, unpinned dependencies, Selenium without a webdriver-manager pin, dynamic access, Vault/Storage imports without recognised calls.

## Limits
Pattern-based. It finds the common `robocorp.vault`, `robocorp.storage`, `RPA.Robocorp.Vault` and `RPA.Robocorp.Storage` call styles. Names built in helper functions or other files show up as `dynamic_access` or a warning; read those lines by hand.

## Side Effects
None. Reads one Project file; no network, no writes.
