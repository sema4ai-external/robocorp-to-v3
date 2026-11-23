# Publish robots from Git to v3

Control Room could publish a robot straight from GitHub or GitLab. On Sema4.ai v3, your CI does it with `rcc cloud push`. v3 speaks the same rcc cloud API that Control Room did, so the rcc you already use works unchanged.

Each push adds a new version to a v3 task package. Workflows always run a package's latest version, so nothing else in v3 needs changing.

This guide has two levels:

1. **[Getting started](#getting-started)**: every push to `main` publishes the robots that changed. One package per robot, a few minutes to set up.
2. **[DEV and PROD](#dev-and-prod)**: merges publish to DEV packages, and a release tag publishes to PROD after someone approves it. It builds on the first level, so start there.

Both use GitHub Actions. GitLab CI is coming next.

## What's in this folder

| File | What it is |
|---|---|
| `taskpackage_sync.py` | Picks the robot folders to publish and runs `rcc cloud push` for each. Downloads rcc and your instance's rcc settings itself. Python standard library only, so it runs on a stock CI runner. |
| `v3-packages.yaml` | The mapping for getting started: which robot folder publishes to which package. |
| `v3-packages-dev-prod.yaml` | The mapping for DEV and PROD. |
| `github/publish-to-v3.yml` | GitHub Actions workflow for getting started. |
| `github/publish-to-v3-dev-prod.yml` | GitHub Actions workflow for DEV and PROD. |

The examples assume this layout in your repository. If yours differs, change the paths in the workflow and the mapping.

```text
your-repo/
├── .github/workflows/publish-to-v3.yml
├── v3-publish/
│   ├── taskpackage_sync.py
│   └── v3-packages.yaml
└── robots/
    ├── invoice-bot/robot.yaml
    └── orders-bot/robot.yaml
```

## Getting started

### 1. Create the task package in v3

Each robot needs a task package to publish to. If you relinked it from Control Room, it already has one. Otherwise, publish it once from v3: upload the robot, or run the `rcc cloud new` command shown in the v3 publish dialog.

Then open the package in v3 and choose **Publish → Publish with rcc**. The "Each version" command holds both ids you need:

```text
rcc cloud push -d <folder> -r <package id> -w <account id>
```

The account id is your v3 workspace. Neither id is a secret.

### 2. Create an access credential

In v3, open your account menu → **Access credentials** and create one. Name it after the repository, for example `github-invoice-robots`, so it is easy to find and revoke later. Copy the `identifier:secret` value. It is shown only once.

The credential is yours: CI publishes as you. See [Good to know](#good-to-know).

### 3. Add the files to your repository

```bash
mkdir -p v3-publish .github/workflows
cp publish-from-git/taskpackage_sync.py publish-from-git/v3-packages.yaml v3-publish/
cp publish-from-git/github/publish-to-v3.yml .github/workflows/
```

Fill in `v3-publish/v3-packages.yaml`, with one entry per robot folder:

```yaml
environments:
  default:
    workspace: 3f1c...        # account id

packages:
  robots/invoice-bot:
    default: 5af1...          # package id
  robots/orders-bot:
    default: cab2...
```

If your robots don't live under `robots/`, also change the `paths:` filter in the workflow.

### 4. Add the secret and the variable

In GitHub, open **Settings → Secrets and variables → Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `V3_RCC_CREDENTIALS` | The `identifier:secret` from step 2 |
| Variable | `V3_URL` | Your v3 address, for example `https://us3.sema4.ai` |

### 5. Push

Commit and push to `main`. Under **Actions → Publish to v3**, the run lists each robot it published:

```text
--- Publishing robots/invoice-bot -> default package 5af1...
OK.
Published robots/invoice-bot to default package 5af1....
```

The package in v3 now has a new version, published by you. On later pushes, only the robots whose folders changed are published. "Run workflow" on the Actions page publishes all of them.

To see what would be published without contacting v3:

```bash
v3-publish/taskpackage_sync.py --base HEAD~3 --dry-run
```

## DEV and PROD

Getting started puts every merge straight into the package your workflows run. For production, keep a DEV package next to it and promote to PROD on purpose.

| Git event | Publishes to | Gate |
|---|---|---|
| Merge to `main` | DEV package of each robot that changed | Protected branch, reviewed pull request |
| Tag `invoice-bot/v1.2.0` | PROD package of that one robot | Protected tags, and approval in the `v3-prod` environment |
| Tag `v1.2.0` | PROD packages of every robot | Same |

This is trunk-based development with promotion by tag, the pattern most enterprises already use to deploy applications:

* **PROD runs exactly what was tested in DEV.** A tag points at a commit that is already on `main`, and so already in DEV. The bundle that reaches PROD is the same one, byte for byte.
* **"What's in PROD?" has a one-word answer:** the latest release tag.
* **Approval and secrets come from GitHub.** The PROD credential lives in the `v3-prod` environment. Only release-tag runs can use it, and only after a reviewer approves.
* **Rollback is a re-run** of the previous tag's release.
* **One repository can hold many robots.** A tag with a robot's name releases only that robot.

We don't recommend a long-lived `dev` branch beside `main`. Promotion then means merging between branches, which drift apart through hotfixes and merges in both directions, and PROD ends up running a merge result that never ran in DEV.

### Where the DEV packages live

| Setup | How | Choose it for |
|---|---|---|
| **Separate DEV and PROD workspaces** (recommended) | Each environment names its own workspace. Package, Vault secret and asset names can be the same in both, because the robot reads whichever workspace it runs in. Each workspace has its own workers and its own credential. | Production processes with real credentials and separate workers. Matches how most Control Room customers split their environments. |
| **Package pairs in one workspace** | Both environments name the same workspace, and each robot has two packages, such as `invoice-bot-dev` and `invoice-bot`. | Small teams and trials. DEV and PROD runs share secrets, assets and workers. |

The mapping file is the same for both; only the ids differ.

### 1. Create the DEV packages

Create a DEV package for each robot, as in [getting started](#1-create-the-task-package-in-v3). With separate workspaces, create them in the DEV workspace. Your existing packages become PROD.

### 2. Create the environments in GitHub

In **Settings → Environments**, create two environments:

* **`v3-dev`**: no rules needed.
* **`v3-prod`**:
  * Under **Required reviewers**, add the people who approve releases.
  * Under **Deployment branches and tags**, choose "Selected branches and tags" and add two tag rules: `*/v*` and `v*`.

Then, in **Settings → Rules → Rulesets**, add a tag ruleset for `*/v*` and `v*` that only release managers may bypass. This stops others from creating, moving or deleting release tags.

In a private repository, environments need GitHub Pro, Team or Enterprise, and required reviewers need GitHub Enterprise Cloud. Without required reviewers, the tag ruleset is the only gate.

### 3. Store the credentials per environment

Add `V3_RCC_CREDENTIALS` as an **environment secret** on both `v3-dev` and `v3-prod`, and delete the repository secret from getting started. Keep `V3_URL` as a repository variable, or set it per environment if DEV and PROD are on different v3 instances.

* Separate workspaces: give each environment the credential of someone who can publish in that workspace.
* Package pairs: the same value can go in both.

An environment secret is given only to jobs that pass that environment's rules. A repository secret is readable by every workflow run, from any branch.

### 4. Switch the mapping and the workflow

Replace your mapping with the shape of `v3-packages-dev-prod.yaml`. Rename `default` to `dev`, and add `prod`:

```yaml
environments:
  dev:
    workspace: <dev account id>
  prod:
    workspace: <prod account id>      # the same id as dev for package pairs

packages:
  robots/invoice-bot:
    release: invoice-bot              # tag prefix; defaults to the folder name
    dev: <dev package id>
    prod: <prod package id>
  robots/experimental-bot:
    dev: <dev package id>             # no prod id: never released to PROD
```

Replace `.github/workflows/publish-to-v3.yml` with `github/publish-to-v3-dev-prod.yml`. Keep the file name, and adjust its `paths:` as before. Push. Changing the mapping publishes every robot to DEV once.

### Releasing

Tag a commit on `main` that has been through DEV, and push the tag:

```bash
git tag invoice-bot/v1.2.0 <commit>
git push origin invoice-bot/v1.2.0
```

The run waits under **Actions** with a "Review deployments" banner. A reviewer opens it, ticks `v3-prod` and approves, and the job publishes that commit to the robot's PROD package. Use `v1.2.0`, with no robot name, to release every robot that has a PROD package.

**Rollback:** open the run of the previous tag and choose **Re-run all jobs**. After approval it publishes that version again, as the newest one.

To check what a tag would release without contacting v3:

```bash
v3-publish/taskpackage_sync.py --environment prod --tag invoice-bot/v1.2.0 --dry-run
```

## Reference

### The mapping file

| Key | Meaning |
|---|---|
| `environments.<name>.workspace` | Account id of the v3 workspace that environment publishes to. Required. |
| `environments.<name>.url` | v3 address for that environment. Optional; defaults to `V3_URL`. |
| `packages.<folder>` | A folder holding `robot.yaml` or `package.yaml`, relative to the repository root. |
| `packages.<folder>.<environment>` | The package id in that environment. A robot with no id for an environment isn't published there. |
| `packages.<folder>.release` | The name in release tags (`<release>/v1.2.0`). Defaults to the folder's last part. |

Package ids stay the same when a package is renamed in v3. The file uses a small subset of YAML (nested `key: value`, comments, quotes), so the script needs no YAML library.

### `taskpackage_sync.py`

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

The script exits with 1 when a publish fails, and with 2 for a setup problem such as a bad tag or a missing id. It keeps rcc's settings in a temporary folder and never prints the credential.

## Good to know

* **The credential is personal, for now.** It publishes as the person who created it, in every workspace where they can publish, and it stops working when they lose that access. Until v3 has workspace-scoped API keys that rcc accepts, use the credential of a person or a dedicated CI user who belongs only to the workspaces CI publishes to. When those keys arrive, only the `V3_RCC_CREDENTIALS` values change.
* **v3 doesn't record which commit a version came from yet.** A version published this way shows "rcc push" and who published it. Until v3 records the commit, the CI run and the release tag are your record of it.
* **v3 also has Publish from GitHub.** A package can be linked to a GitHub repository, branch and folder under **Publish → Publish from GitHub**. Each version is then published by pressing Publish in v3, not on push. A linked package refuses `rcc cloud push`, so choose one method per package.
