# GitLab CI (DRAFT)

> **DRAFT.** These templates follow the same steps as the GitHub workflows, which run against v3, but they have not run on GitLab yet.

The script and the mapping file are the same as on GitHub. Only the CI file and the settings differ.

## Quick start

1. **Get the ids and create a credential**, as in steps 1 and 2 of the [quick start](README.md#quick-start-github).
2. **Add the files.** Copy [`taskpackage_sync.py`](taskpackage_sync.py), [`v3-packages.yaml`](v3-packages.yaml) and [`gitlab/publish-to-v3.gitlab-ci.yml`](gitlab/publish-to-v3.gitlab-ci.yml) into `v3-publish/`. Fill in the ids, then include the job from `.gitlab-ci.yml`:

   ```yaml
   include:
     - local: v3-publish/publish-to-v3.gitlab-ci.yml
   ```

3. **Add the variables.** Under **Settings → CI/CD → Variables**, add `V3_RCC_CREDENTIALS` (Masked and Protected) and `V3_URL`.
4. **Push** to the default branch. **Build → Pipelines → Run pipeline** publishes every robot.

The job runs in the `deploy` stage on the `python:3.12` image, so it needs a Docker-capable runner. GitLab.com's shared runners are Docker-capable.

## DEV and PROD

The lifecycle is the same as in [DEV and PROD](dev-prod.md), with merge requests in place of pull requests. Starting from a working quick start:

1. **Create the DEV packages and workflows** in v3, as on GitHub.
2. **Protect the default branch:** merges only through approved merge requests, with **Pipelines must succeed** on.
3. **Protect the release tags.** Under **Settings → Repository → Protected tags**, protect `*/v*` and `v*` and allow only release managers to create them.
4. **Switch the mapping and the template.** Change the mapping as on GitHub. Replace `v3-publish/publish-to-v3.gitlab-ci.yml` with [`gitlab/publish-to-v3-dev-prod.gitlab-ci.yml`](gitlab/publish-to-v3-dev-prod.gitlab-ci.yml), keeping the file name, and push. GitLab creates the `v3-dev` and `v3-prod` environments.
5. **Scope the credential.** Under **Settings → CI/CD → Variables**, replace `V3_RCC_CREDENTIALS` with two variables of the same name. Give them the environment scopes `v3-dev` and `v3-prod`, and make both Masked and Protected.
6. **Require approval for PROD.** Under **Settings → CI/CD → Protected environments**, protect `v3-prod` and add approvers. This needs GitLab Premium or Ultimate. Without it, the protected tags are the only gate.

| GitHub | GitLab |
|---|---|
| `plan` check on the pull request | `publish-to-v3-plan` job on the merge request |
| `dev` job on push to `main` | `publish-to-v3-dev` job |
| `prod` job on a release tag, after **Review deployments** | `publish-to-v3-prod` job, after approval on the job page or under **Operate → Environments** |
| Rollback: **Re-run all jobs** on the previous tag's run | Rollback: run the previous tag's `publish-to-v3-prod` job again |
