# Reference

## The mapping file

| Key | Meaning |
|---|---|
| `environments.<name>.workspace` | Account id of the v3 workspace that environment publishes to. Required. |
| `environments.<name>.url` | v3 address for that environment. Optional; defaults to `V3_URL`. |
| `packages.<folder>` | A folder holding `robot.yaml` or `package.yaml`, relative to the repository root. |
| `packages.<folder>.<environment>` | The package id in that environment. A robot with no id for an environment isn't published there. |
| `packages.<folder>.release` | The name in release tags (`<release>/v1.2.0`). Defaults to the folder's last part. |

A robot without a task package yet: create one in v3 by uploading the robot, or with the `rcc cloud new` command in the package's **Publish with rcc** dialog. Package ids stay the same when a package is renamed in v3. The file uses a small subset of YAML (nested `key: value`, comments, quotes), so the script needs no YAML library.

## `taskpackage_sync.py`

| Option | Publishes |
|---|---|
| `--base <commit>` | Each mapped robot whose folder changed since `<commit>`. Every robot when `<commit>` is missing, all zeros (a new branch) or unknown, or when the mapping file changed. |
| `--tag <tag>` | `<release>/v…` publishes that robot; `v…` publishes every robot in the environment. Any other tag is an error. |
| `--all` | Every mapped robot. |
| `--environment <name>` | Which environment in the mapping. Optional when the mapping names only one. |
| `--mapping <file>` | Another mapping file. The default is `v3-packages.yaml` next to the script. |
| `--dry-run` | Prints what would be published, without contacting v3. |

| Environment variable | Meaning |
|---|---|
| `V3_RCC_CREDENTIALS` | The access credential, `identifier:secret`. |
| `V3_URL` | The v3 address, for example `https://us3.sema4.ai`. |
| `RCC_VERSION` | rcc to download when it isn't on `PATH`. Default `v19.0.1`. |
| `V3_PACKAGES_FILE` | The mapping file, when not passed with `--mapping`. |

The script exits with 1 when a publish fails, and with 2 for a setup problem such as a bad tag or a missing id. It keeps rcc's settings in a temporary folder and never prints the credential.

## Current limits

* **The credential is personal, for now.** It publishes as the person who created it, in every workspace where they can publish, and it stops working when they lose that access. Until v3 has workspace-scoped API keys that rcc accepts, use the credential of a person or a dedicated CI user who belongs only to the workspaces CI publishes to. When those keys arrive, only the `V3_RCC_CREDENTIALS` values change.
* **v3 doesn't record which commit a version came from yet.** A version published this way shows "rcc push" and who published it. Until v3 records the commit, the CI run and the release tag are your record of it.
* **v3 also has Publish from GitHub.** A package can be linked to a GitHub repository, branch and folder under **Publish → Publish from GitHub**. Each version is then published by pressing Publish in v3, not on push. A linked package refuses `rcc cloud push`, so choose one method per package.
