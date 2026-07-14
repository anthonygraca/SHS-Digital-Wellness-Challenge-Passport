# AWS CLI + S3 Walkthrough

An introductory tour of the AWS CLI, using the bucket `dxhub-camp-2026-csub-shs-digital-wellness` as a live example.

Every command we run gets logged here with what it does and why you'd use it.

## Setup / Identity

| Command | Use case |
|---|---|
| `aws --version` | Confirms the CLI is installed and shows which version (useful for troubleshooting version-specific flags/bugs). |
| `aws sts get-caller-identity` | Shows *who* the CLI is currently authenticated as — your IAM/SSO identity, account ID, and assumed role ARN. Always a good first sanity check before running anything else. |

## Discovering buckets

| Command | Use case |
|---|---|
| `aws s3 ls` | Lists all S3 buckets visible to your current identity, across the whole account. Your starting point when you don't know bucket names yet. |
| `aws s3api get-bucket-location --bucket <name>` | Returns the AWS region a bucket lives in. Useful because some commands (and performance) are region-sensitive, and S3 URLs/endpoints differ by region. |

## Exploring bucket contents

| Command | Use case |
|---|---|
| `aws s3 ls s3://<bucket>/` | Lists top-level "folders" (prefixes) and objects in a bucket. S3 has no real folders — this just shows keys grouped by `/` delimiters. |
| `aws s3 ls s3://<bucket>/ --recursive --human-readable` | Lists every object in the bucket (all nested prefixes), with sizes in human-readable units (KiB/MiB) instead of raw bytes. |
| `aws s3 ls s3://<bucket>/ --recursive --summarize --human-readable` | Same as above, plus a summary footer with total object count and total size — quick way to gauge bucket size/cost footprint. |

## Security posture

| Command | Use case |
|---|---|
| `aws s3api get-public-access-block --bucket <name>` | Shows whether the account/bucket blocks public ACLs and policies. All-`true` means the bucket cannot be made public even by accident/misconfiguration — the strongest S3 safety net. |
| `aws s3api get-bucket-policy --bucket <name>` | Shows the resource-based JSON policy attached to the bucket (who/what can access it, from where). `NoSuchBucketPolicy` error just means none is set — not a failure. |
| `aws s3api get-bucket-acl --bucket <name>` | Shows the legacy ACL grant list (older, coarser access-control mechanism than bucket policies). Good to check nobody's granted `AllUsers`/`AuthenticatedUsers` read/write. |
| `aws s3api get-bucket-encryption --bucket <name>` | Shows the default server-side encryption applied to new objects (e.g. `AES256` or `aws:kms`). Confirms data at rest is encrypted by default. |
| `aws s3api get-bucket-versioning --bucket <name>` | Shows whether object versioning is enabled. Empty response = disabled (deleting/overwriting an object is permanent, no history kept). |
| `aws s3api get-bucket-logging --bucket <name>` | Shows whether S3 server access logging is enabled (records every request made against the bucket to another bucket). Empty response = disabled. |
| `aws s3api get-bucket-lifecycle-configuration --bucket <name>` | Shows rules that auto-transition or auto-expire objects (e.g. move to Glacier after 90 days). `NoSuchLifecycleConfiguration` error just means none is set. |
| `aws s3api get-bucket-tagging --bucket <name>` | Shows cost-allocation/organizational tags on the bucket. `NoSuchTagSet` error just means none is set. |

### Findings for `dxhub-camp-2026-csub-shs-digital-wellness`

- **Public access block:** all 4 settings `true` — bucket cannot be made public, even by accident.
- **Bucket policy:** none set.
- **ACL:** only the owner has `FULL_CONTROL`; no public/external grants.
- **Encryption:** enabled by default (`AES256`).
- **Versioning:** disabled — deletes/overwrites are not recoverable via S3 itself.
- **Logging:** disabled — no built-in access log trail.
- **Lifecycle rules:** none — objects stay in Standard storage indefinitely (no auto-archival/expiry).
- **Tags:** none.

**Takeaway:** the bucket is locked down from public access and encrypted at rest, which is the important part. Versioning is off, so treat deletes as permanent — worth turning on if these campaign assets (recording, PDFs) are hard to reproduce.

## Downloading contents locally

| Command | Use case |
|---|---|
| `aws s3 sync s3://<bucket>/ <local-dir>/` | Mirrors the entire bucket (all keys/prefixes) into a local directory, preserving the folder structure. Only copies new/changed files on repeat runs (unlike `cp`, which always re-copies everything) — the standard way to pull down or back up a whole bucket. `--exclude "<pattern>"` skips matching files. |

We ran this to pull all 6 objects (`data/`, `testimonials/`) down into this project directory for local inspection.

---

*(more commands will be appended below as we go)*
