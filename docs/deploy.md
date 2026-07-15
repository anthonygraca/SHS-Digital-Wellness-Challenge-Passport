# Deployment playbook

A demo deployment: one EC2 host running the app as a single container, on a stable
address, that you can turn off when nobody is looking at it.

> **This file is committed to a public repository.** It uses placeholders, never real
> identifiers. Account ids, instance ids and addresses live in `.deploy-local/env`
> (git-ignored), which `provision.sh` writes for you. Don't paste real values into this
> file, into issues, or into commit messages.

## The short version

```bash
source .deploy-local/env          # once per shell

scripts/deploy/status.sh          # what's running, who can reach it, what it costs
scripts/deploy/up.sh              # turn it on   (~1 min)
scripts/deploy/down.sh            # turn it off  (stops the bill, keeps the data)
scripts/deploy/release.sh         # ship the current commit
scripts/deploy/access.sh public   # let anyone reach it
scripts/deploy/access.sh me       # lock it back to your IP
scripts/deploy/logs.sh            # app logs, no SSH key needed
scripts/deploy/destroy.sh         # delete everything, including the data
```

## First-time setup

```bash
aws sso login
scripts/deploy/provision.sh       # ~3 min; writes .deploy-local/env
scripts/deploy/release.sh         # build, push, roll out
scripts/deploy/access.sh public   # if you want to share it
```

`provision.sh` creates an ECR repository, an IAM role and instance profile, a security
group, an Elastic IP, and one `t3.small`. It is safe to re-run; it skips what exists.

## Turning it off and on

This is the part worth internalising, because **stop is not terminate**:

| | Billing | Data | URL | Reversible |
|---|---|---|---|---|
| `down.sh` (stop) | compute stops | kept on EBS | kept | yes — `up.sh`, ~1 min |
| `destroy.sh` (terminate) | everything stops | **deleted** | released | no |

While stopped you still pay a few cents a month for the EBS volume and ~$0.005/hr for
the Elastic IP, because AWS charges for an address reserved but not attached to a
running instance. That is the price of the URL not changing, and it is worth it: a plain
public IP is released on every stop, so without the Elastic IP every link you had shared
would break the first time you turned it off. Verified: stop → start returns the same
address in about a minute with the database intact.

Nothing else is needed after a restart. A `wellness-passport.service` systemd unit
re-authenticates to ECR (its credentials are short-lived — the re-login in `ExecStartPre`
is load-bearing) and brings the stack back up on boot.

## Shipping a new version

```bash
scripts/deploy/release.sh
```

Builds the image, tags it with the current git SHA **and** `:latest`, pushes both, then
rolls the instance onto it over SSM. The SHA tag is what makes a running deployment
traceable back to a commit; `:latest` is what lets the host's compose file stay static.
A dirty tree is tagged `-dirty` so you can tell a real release from a hack.

`release.sh` refuses to declare success unless three things hold: `/healthz` answers, `/`
returns HTML (see "the SPA mount" below), and `/api/version` reports the SHA it just
built. That last check exists because "the rollout succeeded" and "the new code is
running" are different claims — the SSM command exits 0 if compose ran at all, so a pull
that kept a cached `:latest` or a container that never recreated both look like success.

## Which build is deployed?

```bash
curl -s http://<host>/api/version      # {"version":"0.1.0","gitSha":"a1b2c3d","builtAt":"..."}
scripts/deploy/status.sh               # prints the same SHA under "commit:"
```

The same SHA is also stamped, quietly, at the bottom of the sign-in screen — so anyone
looking at the app, including a stakeholder on a phone, can say which build they are
looking at without your help.

An **unstamped** build reports `"unknown"` and shows nothing on the sign-in screen. That
is correct and expected: only `release.sh` passes the build args, so a plain
`docker build .` or a local `uvicorn` has no SHA to claim. A `-dirty` suffix means the
image was built from an uncommitted tree and matches no commit.

## How it fits together

**One image, not two.** The SPA and API must share an origin: every client call uses a
relative path (`import.meta.env.VITE_API_BASE ?? ""`) and the session cookie is HttpOnly
/ SameSite=Lax. On a split origin the cookie is silently not sent and sign-in fails with
nothing pointing at the cause. So the `Dockerfile` builds the SPA with Node and copies
`dist/` into the Python image, which serves it. No nginx, no proxy, no CORS.

**The SPA mount is load-bearing and has been reverted once already.** `/auth/callback`,
`/home`, `/passport` and `/admin/*` are React Router routes with no file on disk;
`SpaStaticFiles` in `app/main.py` falls back to `index.html` for them. It deliberately
does *not* fall back for `api/`, `enrollment`, `mock-idp/` or `healthz` — a miss there
must stay a JSON 404, or an API client gets HTML at HTTP 200 and `res.json()` chokes.
If that mount goes missing in a merge, the image builds fine and serves only the API;
`release.sh`'s HTML check is there to catch exactly that.

**No SSH key, no port 22.** Shell access is via SSM Session Manager, which the instance
role grants:

```bash
aws ssm start-session --target "$INSTANCE_ID" --region "$AWS_REGION"
```

**Persistence** is SQLite on a named Docker volume (`wp-data` → `/data`) on the instance's
EBS root. The image overrides `WP_DATABASE_URL` to an **absolute** path; the default in
`config.py` is relative and would land inside the container and die with it.

## Access control

`access.sh` replaces the ingress rules rather than adding to them, so the security group
always says exactly one thing about who can get in.

IP allowlisting is brittle in practice — a laptop that moves between home and campus gets
a new address and locks itself out. `access.sh me` re-pins to wherever you are now.

## What is deliberately insecure, and what that does and doesn't mean

`WP_AUTH_PROVIDER=mock` serves a fake IdP at `/mock-idp/login` that mints a session for
any identity submitted, including `affiliation=staff`. **This is the point** — it is how
the stakeholder use cases are demonstrated without a real campus IdP.

What that gets an anonymous visitor is **app-admin: reading and editing challenge and
report data**. It is not a foothold on the VM, and it is worth being precise about why:

- No RCE sinks anywhere in the app — no `subprocess`, `eval`, `exec`, `pickle`, `shell=True`.
- No SQL injection — every query is a SQLAlchemy `select()` construct; `text()` is never used.
- No file writes, no uploads, no outbound HTTP, so no SSRF and no path traversal.
- The Docker socket is not mounted into the container.
- The instance requires IMDSv2 (`HttpTokens=required`), which is the usual route from an
  app-level bug to stolen instance credentials.
- The instance role carries only ECR-read and SSM.

So the realistic risk of running this publicly is **demo integrity** — a stranger editing
your seed data before a stakeholder walkthrough — not compromise of the host or the
account. If that matters on a given day, `access.sh me` before the demo.

`WP_JWT_SECRET` and `WP_QR_SECRET` are left at the dev defaults committed to this repo on
the current box, which makes session cookies forgeable. That sounds worse than it is: the
mock IdP already grants admin to anyone who asks, so forgery is a second key to an
unlocked door. It starts mattering the moment `WP_AUTH_PROVIDER=mock` goes away — at
which point it is a blocker, not a nicety. `provision.sh` generates real secrets for
fresh deployments because there it costs nothing.

> Note: `provision.sh` bakes those secrets into EC2 user-data, which is readable from the
> instance via IMDS and via `describe-instance-attribute` with account credentials. Fine
> for demo data; move to Secrets Manager or SSM Parameter Store before anything real.

See the deployment issue for the full gap list — fail-closed config, migrations, and why
`WP_AUTH_PROVIDER=saml` does not work yet.

## Cost

Roughly `$0.02/hr` for the `t3.small` while running, plus pennies a day for EBS and the
Elastic IP. Left running continuously that is about `$15/month`; `down.sh` between demos
takes it to nearly nothing. `status.sh` prints the current state and a reminder.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `up.sh` starts but `/healthz` never answers | Security group doesn't allow your current IP. `access.sh me`. |
| `/` returns JSON or 404 instead of the app | The `SpaStaticFiles` mount is missing from `app/main.py`. |
| Sign-in redirects but no session | Cookie dropped — check the SPA and API are on one origin. |
| Host never came up at all | `logs.sh boot` for the cloud-init bootstrap log. |
| `release.sh` says not authenticated | `aws sso login`. |
