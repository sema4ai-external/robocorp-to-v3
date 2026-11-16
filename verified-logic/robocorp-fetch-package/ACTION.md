# Robocorp Fetch Package

## Purpose
Download one task package from Control Room into the Project for step 5 ("Code peek") of the `robocorp-relink` skill. Feed the zip to `robocorp-code-peek`, and later to `task_engine.add_package`.

## Prerequisites (in the calling Project)
- The same network credential as `robocorp-inventory` (`ROBOCORP_API`).
- Allowlist `cloud.robocorp.com:443` **and the package storage host**, an S3 bucket host such as `eu1-….s3.eu-west-1.amazonaws.com`. If it is missing, the error names the exact host to add.

## Inputs
- `workspace_id`, `package_id` (required).
- `output_dir`: default `relink/packages`.

## Output
`zip_path`, `metadata_path`, task names, size, sha256, the storage host, and the file list.

## Side Effects
- One GET to Control Room and one download from its storage. The signed download link is used once and never written to a file or returned. No Authorization header is sent to the storage host.
- Writes `<output_dir>/<package-name>.zip` and `.json`.

## Limits
Packages over 12 MiB are refused (Verified Logic file limit); download those by hand.
