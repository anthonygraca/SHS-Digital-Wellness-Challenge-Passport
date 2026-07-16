# Serverless Backend Guide — FastAPI on AWS Lambda + API Gateway + DynamoDB

A beginner-friendly, step-by-step walkthrough for deploying the SHS Wellness
Passport backend to AWS as a set of **serverless** functions, using **AWS SAM**.

If you can run terminal commands but have never touched AWS serverless before,
this guide is for you. We explain each concept the first time it appears, then
show you exactly what to run.

> **Where this fits.** This backend is the *second origin* of the single
> CloudFront distribution described in the frontend guide,
> [`docs/cloudfront-deploy-guide.md`](./cloudfront-deploy-guide.md). The frontend
> (a static React app on S3) and this backend live behind **one** CloudFront
> domain so the browser only ever talks to one origin — that keeps the app
> "same-origin," which is what makes relative API paths (`/api/*`, `/auth/*`,
> `/enrollment`) and the session cookie work with **no CORS** and **no frontend
> URL changes**. Deploy this backend first (or the frontend first — they are
> independent), then come back to the frontend guide's steps 5–6 to wire the two
> together.

---

## 1. Concepts (read this once, it's short)

Our backend today is a normal FastAPI app that you run with `uvicorn` and that
stores data in a local SQLite file. "Serverless" means we stop running a
long-lived server and instead let AWS run our code on demand. Here are the five
pieces and **why this particular app fits them so cleanly**.

### AWS Lambda — "run this function when someone calls it"
A **Lambda function** is code that AWS runs only when it's invoked, then throws
the container away. You pay per request and per millisecond, nothing while idle.
The catch: a function can be started fresh at any time and **must not rely on
anything kept in memory between requests**.

*Why this app is Lambda-safe:* our authentication is a **stateless HS256 JWT**
stored in the `wp_session` cookie (`backend/app/auth/session.py`). There is **no
server-side session store** — every request re-validates the signed cookie on its
own. So it does not matter which fresh Lambda container handles a request. The
only things that must persist are the data tables (→ DynamoDB) and the two signing
secrets (`WP_JWT_SECRET`, `WP_QR_SECRET`), which we pass in as configuration.

### API Gateway (HTTP API) — "the front door that turns URLs into function calls"
Lambda functions don't have URLs by themselves. **API Gateway** gives us a public
HTTPS endpoint and **routes each incoming path to a function**. We use the
cheaper, simpler flavor called **HTTP API** (as opposed to the older "REST API").

- It comes with a **managed TLS certificate**, so CloudFront can use it as a
  secure HTTPS origin with no self-signed-cert headaches.
- We deploy to the **`$default` stage** — the stage whose URL has **no**
  stage-name path segment, so `/api/passport` passes through unchanged (instead
  of becoming `/prod/api/passport`).
- Routing is **per-path**: `/auth/{proxy+}` → one function, `/api/passport` →
  another, etc.

### DynamoDB — "a managed NoSQL table, no server to run"
**DynamoDB** is AWS's serverless NoSQL database. You define tables with a
**primary key** and optional **secondary indexes (GSIs)** for alternate lookups.
We run every table in **PAY_PER_REQUEST** (a.k.a. "on-demand") mode: no capacity
to provision, no cost while idle.

*Why one table per entity:* we mirror today's six SQLite tables as six DynamoDB
tables (plus a tiny `Counters` table). This gives a 1:1 mapping to the current
schema **and** lets us grant each Lambda function access to **only the tables it
needs** — clean, table-level, least-privilege IAM.

### AWS SAM — "describe all of this in one file and deploy it as a unit"
**SAM (Serverless Application Model)** is Infrastructure-as-Code for serverless
apps. You write one `template.yaml` describing the functions, the HTTP API, the
tables, the permissions, and the environment variables; then `sam build` packages
the code and `sam deploy` creates/updates everything as one **CloudFormation
stack**. We use SAM (not console clicks) because Lambda + HTTP API + DynamoDB +
IAM + env are too interdependent to click together reliably.

### Lambda Layer — "shared code, uploaded once"
A **Lambda Layer** is a zip of shared libraries/code that multiple functions
attach to, so you don't duplicate it in every function bundle. We ship the entire
`app/` package (config, auth deps, repositories, schemas, services) **plus its
dependencies** as one shared layer; each of the four functions is then a tiny
entrypoint that imports from the layer.

### Why split into per-route functions?
We split the API into **four functions along router / bounded-context lines**
(auth, enrollment, passport, challenges), not one monolith. The tradeoff we accept
is **four independent cold starts** (each only when its routes are first hit). In
return, per-function IAM is genuinely clean: `passport-fn` gets **no write** on
`Challenges`; `auth-fn` only ever touches `Students`. Because the tables are split
per entity, the permission boundaries fall out naturally.

---

## 2. Prerequisites

You need three tools installed locally, plus an AWS account you can log into from
the terminal.

### 2.1 AWS CLI (configured with credentials)
The AWS CLI lets you talk to AWS from the terminal. SAM uses your CLI credentials
to deploy.

```bash
# macOS (Homebrew)
brew install awscli

# Verify
aws --version
```

> **Other OSes:** Windows — download the MSI installer from AWS; Linux — use the
> official `awscli-exe-linux` bundle. See AWS's "Install the AWS CLI" docs.

Configure credentials (an access key from your AWS account, IAM user, or SSO):

```bash
aws configure
# AWS Access Key ID:     <your key>
# AWS Secret Access Key: <your secret>
# Default region name:   us-west-2
# Default output format:  json

# Verify it works — prints your account id
aws sts get-caller-identity
```

### 2.2 AWS SAM CLI
Builds and deploys the serverless stack, and can run the API locally.

```bash
# macOS (Homebrew)
brew install aws-sam-cli

# Verify
sam --version
```

> **Other OSes:** Windows — the AWS SAM CLI MSI installer; Linux — the AWS SAM CLI
> zip or Homebrew-on-Linux. See AWS's "Install the AWS SAM CLI" docs.

### 2.3 Docker
`sam build` compiles the Python dependencies inside a Lambda-like container (so
native wheels match the Lambda runtime), and we run **DynamoDB Local** in a Docker
container for offline testing. Docker must be **installed and running**.

```bash
# macOS (Homebrew) — installs Docker Desktop
brew install --cask docker
# Then launch Docker Desktop once so the daemon is running.

# Verify the daemon is up
docker ps
```

> **Other OSes:** Windows/macOS — Docker Desktop; Linux — Docker Engine
> (`docker.io` / the official Docker repo).

---

## 3. The code structure this deployment expects

You do **not** create `template.yaml` or the function/repository code from this
guide — those are produced separately (see the plan's Workstream 2). This section
describes what the deployment *expects to find* so the commands below make sense.

### 3.1 Shared Layer + per-function entrypoints
```
backend/
  app/
    main.py                  # unchanged: all-routers app for `make dev` / uvicorn
    config.py                # gains WP_PERSISTENCE, table names, aws_region
    routers/                 # auth, enrollment, passport, challenges (unchanged)
    services/                # business logic, refactored to call a repository
    repositories/
      base.py                # Repository Protocol (interface)
      sqlalchemy_repo.py     # SQLite path — used by tests + `make dev`
      dynamo_repo.py         # boto3 path — used in Lambda
    functions/               # ← the Lambda entrypoints
      auth.py                #   app = make_app(auth.router);       handler = Mangum(app)
      enrollment.py          #   app = make_app(enrollment.router); handler = Mangum(app)
      passport.py            #   app = make_app(passport.router);   handler = Mangum(app)
      challenges.py          #   app = make_app(challenges.router); handler = Mangum(app)
```

Each entrypoint is a **slim FastAPI app that includes only its own router**,
wrapped by **Mangum** (`handler = Mangum(app)`). Mangum is the adapter that lets
API Gateway's event format drive a standard ASGI/FastAPI app — it's why we can run
the *exact same FastAPI code* in Lambda that we run locally under uvicorn. The
`app/` package and its dependencies (including `mangum` and `boto3`) live in the
**shared Layer**; `python3-saml`/`xmlsec` are **excluded** from Lambda packages
(the auth provider defaults to `mock` and SAML is only lazily imported).

### 3.2 Environment variables the functions read
All settings use the `WP_` prefix (see `backend/app/config.py`). The Dynamo path
is turned on with `WP_PERSISTENCE=dynamo`; the SQLite path (`WP_PERSISTENCE=sql`,
the default) stays for local dev and tests.

| Variable | Purpose |
|---|---|
| `WP_PERSISTENCE=dynamo` | Selects the DynamoDB repository (default `sql`). |
| `WP_DDB_TABLE_PREFIX` | Prefix for the DynamoDB table names (default `wp-`). Must match the SAM `TablePrefix`, so the repo talks to `wp-Students`, `wp-Challenges`, … |
| `WP_DDB_ENDPOINT_URL` | DynamoDB endpoint override — set to `http://host.docker.internal:8000` for DynamoDB Local; leave **unset** in the cloud so boto3 uses the real regional endpoint. |
| `WP_JWT_SECRET` | HS256 secret for the `wp_session` JWT. **Must be stable across invocations.** |
| `WP_QR_SECRET` | HS256 secret for event-QR tokens. Kept separate so rotating one never invalidates the other. |
| `WP_AUTH_PROVIDER` | `mock` (demo IdP, the default) or `saml` (real campus IdP). Keep `mock` for the demo. |
| `WP_COOKIE_SECURE` | Marks the `wp_session` cookie `Secure` (`true` behind CloudFront HTTPS). |

### 3.3 `template.yaml` at a glance
The SAM template (created separately) contains:

- **One `AWS::Serverless::LayerVersion`** — the shared `app/` package + deps.
- **Four `AWS::Serverless::Function`s** (`auth-fn`, `enrollment-fn`,
  `passport-fn`, `challenges-fn`), Python **3.12**, handler
  `app.functions.<name>.handler`, each attached to the shared layer. Each function
  declares:
  - **`HttpApi` `Events`** for *its own* routes on the **`$default` stage**;
  - a **per-function `Policies`** block granting **only its tables**
    (`DynamoDBReadPolicy` / `DynamoDBCrudPolicy` per table);
  - env vars: `WP_PERSISTENCE=dynamo`, the table names, and the secrets it needs.
  - Optionally a fifth `health-fn` for `/healthz`.
- **Six/seven `AWS::DynamoDB::Table`s**, all **PAY_PER_REQUEST**, with the GSIs
  listed in §3.5.
- **Secrets as SAM parameters** wired into the functions' env (see §9 for the
  production upgrade to Secrets Manager / SSM).

### 3.4 Function → routes → tables → secrets

| Function | API Gateway routes | Guard | Tables (→ least-privilege IAM) | Secrets |
|---|---|---|---|---|
| `auth-fn` | `/auth/{proxy+}`, `/mock-idp/{proxy+}` | public | `Students` RW | `WP_JWT_SECRET` |
| `enrollment-fn` | `/enrollment` | current student | `Enrollments` RW; `Challenges` read | `WP_JWT_SECRET` |
| `passport-fn` | `/api/passport`, `/api/checkins`, `/api/checkins/scan` | current student | `CheckIns` RW; `Challenges` + `Tasks` read | `WP_JWT_SECRET`, `WP_QR_SECRET` |
| `challenges-fn` | `/api/challenges/{proxy+}` | admin | `Challenges` + `Tasks` + `AssessmentItems` RW; `Counters` update | `WP_JWT_SECRET` |
| `health-fn` *(optional)* | `/healthz` | public | none | none |

Note there is **no 1:1 route→table mapping**: one call can touch several tables.
For example `GET /api/passport` (passport-fn) reads `Challenges` (active) +
`Tasks` (ordered) + `CheckIns` (this student); `POST /api/challenges/{id}/tasks`
(challenges-fn) does `Counters.UpdateItem` (new id) + `Tasks.PutItem`.

### 3.5 The six/seven DynamoDB tables

| Table | Key schema | GSIs |
|---|---|---|
| `Students` | PK `student_id`(S) = `<campus>#<sso>` | — |
| `Challenges` | PK `id`(N) | `ByCampus` (PK `campus_id`, SK `created_at`); `PublishedByCampus` **sparse** (PK `pub_campus_id`, SK `start_date#created_at`) |
| `Tasks` | PK `id`(N) | `ByChallenge` (PK `challenge_id`, SK `position`) |
| `AssessmentItems` | PK `id`(N) | `ByTask` (PK `task_id`); `ByChallenge` (PK `challenge_id`) |
| `Enrollments` | PK `student_id`(S), SK `challenge_id`(N) | — |
| `CheckIns` | PK `student_id`(S), SK `task_id`(N) | — |
| `Counters` | PK `name`(S) ∈ {challenge, task, item} | — |

`student_id` is `"<campus>#<sso_subject>"` (carried in the JWT, never exposed in
API responses). DynamoDB has no uniqueness constraints, so the app re-implements
them with **conditional writes** (`attribute_not_exists`) on each table's natural
key — that is what gives us idempotent enroll, duplicate-check-in → 409, and
get-or-create student. Integer IDs are preserved for challenges/tasks/items via
the `Counters` table (`UpdateItem ADD seq :1`).

---

## 4. Local testing (before you deploy)

Test the whole thing on your laptop first. There are two independent things to keep
green: the **SQLite/SQLAlchemy path** (tests) and the **DynamoDB path** (the real
Lambda code path).

### 4.1 Keep the SQLite test suite green
The refactor keeps the SQLAlchemy repository for local dev and the existing pytest
suite. This runs with `WP_PERSISTENCE=sql` (the default), so it needs no AWS at
all:

```bash
make test-api      # cd backend && .venv/bin/pytest -q
```

Keep this **green** throughout — it's your regression net for the business logic
(sequential-unlock, position math, idempotency) that is shared across both
persistence paths.

### 4.2 Run DynamoDB Local (Docker)
DynamoDB Local is a container that behaves like DynamoDB on `localhost:8000`, so
you can exercise the `dynamo_repo` path offline and for free.

```bash
# Start DynamoDB Local, listening on port 8000
docker run -d --name dynamodb-local -p 8000:8000 amazon/dynamodb-local

# Sanity check it's up (should return an empty TableNames list at first)
aws dynamodb list-tables --endpoint-url http://localhost:8000 --region us-west-2
```

> The `--endpoint-url http://localhost:8000` flag is what tells the AWS CLI (and
> boto3) to talk to your local container instead of real AWS. DynamoDB Local
> ignores credentials, but the CLI still wants *some* — any dummy values in
> `aws configure` are fine for local work.

### 4.3 Create the tables locally
Create each of the six/seven tables (matching §3.5) against the local endpoint.
Example for one table — repeat with the right key schema / GSIs for each:

```bash
aws dynamodb create-table \
  --endpoint-url http://localhost:8000 --region us-west-2 \
  --table-name CheckIns \
  --attribute-definitions \
      AttributeName=student_id,AttributeType=S \
      AttributeName=task_id,AttributeType=N \
  --key-schema \
      AttributeName=student_id,KeyType=HASH \
      AttributeName=task_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

> Tip: don't hand-type all seven `create-table` calls — this repo ships
> **`scripts/create_tables_local.sh`**, which creates every table (with the right
> GSIs, matching `template.yaml`) against DynamoDB Local. Just run it:
>
> ```bash
> scripts/create_tables_local.sh          # prefix wp-, endpoint http://localhost:8000
> ```

### 4.4 Run the API locally with `sam local start-api`
`sam local start-api` stands up the whole HTTP API on your machine, running each
function in a Lambda-like Docker container and routing paths exactly as API
Gateway will in the cloud.

```bash
# Build once (packages deps into a Lambda-compatible bundle; needs Docker)
sam build

# Serve the API locally on http://127.0.0.1:3000
# Point the functions at DynamoDB Local and select the Dynamo path.
sam local start-api \
  --env-vars env.local.json
```

A minimal `env.local.json` (one block per function, matching the logical IDs in
`template.yaml`) sets the Dynamo path and the local endpoint. Conceptually:

```jsonc
{
  "Parameters": {
    "WP_PERSISTENCE": "dynamo",
    "WP_DDB_TABLE_PREFIX": "wp-",
    "WP_DDB_ENDPOINT_URL": "http://host.docker.internal:8000",
    "WP_AUTH_PROVIDER": "mock",
    "WP_JWT_SECRET": "local-dev-32byte-minimum-secret-value-aaaa",
    "WP_QR_SECRET":  "local-dev-32byte-minimum-secret-value-bbbb"
  }
}
```

> On macOS, containers reach your host's DynamoDB Local at
> `http://host.docker.internal:8000` (not `localhost`, which inside the container
> points at the container itself). The Dynamo repo reads its endpoint override
> from **`WP_DDB_ENDPOINT_URL`** for exactly this reason — set it to
> `http://host.docker.internal:8000` for local runs (as in the `env.local.json`
> above), and leave it unset in the cloud so boto3 uses the real regional endpoint.

Now exercise it:

```bash
# Health check (public)
curl http://127.0.0.1:3000/healthz
# → {"status":"ok"}

# Not signed in yet → 401 JSON (proves the guard + routing work)
curl -i http://127.0.0.1:3000/auth/session
```

Walk through mock login, enroll, passport read, and a check-in locally. When that
all behaves, you're ready to deploy.

---

## 5. Deploy with SAM

### 5.1 Build
```bash
sam build
```
This packages each function and the shared layer using Docker so native wheels
match the Lambda Python 3.12 runtime. Output goes to `.aws-sam/build/`.

### 5.2 Guided deploy (first time)
```bash
sam deploy --guided
```
SAM asks a series of questions. Sensible answers for this project:

| Prompt | What to answer | Why |
|---|---|---|
| **Stack Name** | `shs-wellness-passport-backend` | The CloudFormation stack name; groups all resources. |
| **AWS Region** | `us-west-2` | Match the frontend/S3 region so everything is co-located. |
| **Parameter `WP_JWT_SECRET`** | your real 32B+ secret | Passed into the functions' env (see §9). |
| **Parameter `WP_QR_SECRET`** | your real 32B+ secret | Separate secret for QR tokens. |
| **Parameter `WP_AUTH_PROVIDER`** | `mock` | Keep the demo IdP unless wiring real SAML. |
| **Confirm changes before deploy** | `y` | Review the changeset before it applies. |
| **Allow SAM CLI IAM role creation** | `y` (`CAPABILITY_IAM`) | The template creates the per-function IAM roles/policies; deploy fails without this capability. |
| **Disable rollback** | `n` | Roll back on failure so you never get a half-created stack. |
| **Save arguments to samconfig.toml** | `y` | Persists your answers so future deploys are just `sam deploy`. |

> **Where the secrets go.** Because the template declares `WP_JWT_SECRET` and
> `WP_QR_SECRET` as **SAM parameters**, `--guided` prompts for them here and wires
> them into each function's environment. They must be **real, high-entropy,
> 32-byte-or-longer** values and **identical across deploys** — see §9.

### 5.3 Subsequent deploys
```bash
sam build && sam deploy      # reuses samconfig.toml
```

### 5.4 Find the HTTP API endpoint URL
The template exports the HTTP API base URL as a stack **Output**. After a
successful deploy, SAM prints the Outputs table; you can also fetch it anytime:

```bash
aws cloudformation describe-stacks \
  --stack-name shs-wellness-passport-backend \
  --region us-west-2 \
  --query "Stacks[0].Outputs" --output table
```

Look for the output whose value looks like:

```
https://<api-id>.execute-api.us-west-2.amazonaws.com
```

**Copy this URL — you need it in two places:** the seed step (§6) and the
CloudFront wiring (§7).

---

## 6. Seed the demo data

Locally, the app used to seed a demo challenge + tasks on startup
(`init_db()` → `seed_demo_challenge`). On the Dynamo path that startup seeding is
**dropped** (tables are created by SAM, not the app), so you seed **once, by hand,
after the first deploy** using the one-off script:

```bash
# Run once, after `sam deploy` succeeds.
# It writes the demo challenge + its 7 tasks straight through the Dynamo repo.
python scripts/seed_dynamo.py
```

> The script writes to the **real** DynamoDB tables in `us-west-2`, so it uses your
> AWS CLI credentials (no `--endpoint-url`). If you also want demo data in
> DynamoDB Local, run it with the local endpoint configured, the same way §4
> pointed boto3 at `http://localhost:8000`. Running it more than once is safe —
> the conditional writes make it idempotent.

Confirm the rows landed:

```bash
aws dynamodb scan --table-name Challenges --region us-west-2 \
  --query "Count"
aws dynamodb scan --table-name Tasks --region us-west-2 \
  --query "Count"   # → 7
```

---

## 7. Wire it into CloudFront

The backend is now live at its API Gateway URL, but the browser should still only
ever talk to the **CloudFront** domain. Add API Gateway as CloudFront's **second
origin** and route the API paths to it.

Follow **[`docs/cloudfront-deploy-guide.md`](./cloudfront-deploy-guide.md), steps
5–6**:

- **Step 5 — Second origin = API Gateway.** Origin domain =
  `<api-id>.execute-api.us-west-2.amazonaws.com` (from §5.4, without the
  `https://` and without any path), Protocol **HTTPS only**, port **443**, origin
  path empty.
- **Step 6 — API behaviors.** Create these path-pattern behaviors (first match
  wins; `/auth/callback` must come **before** `/auth/*`). Every API behavior uses
  cache policy **CachingDisabled** and origin request policy
  **AllViewerExceptHostHeader** (NOT AllViewer — API Gateway rejects a forwarded
  CloudFront Host header; ExceptHostHeader still forwards cookies + query string,
  which auth needs), and allows methods GET/HEAD/OPTIONS/PUT/POST/PATCH/DELETE:

  | # | Path pattern     | Origin       |
  |---|------------------|--------------|
  | 1 | `/auth/callback` | S3 (SPA route) |
  | 2 | `/api/*`         | API Gateway  |
  | 3 | `/auth/*`        | API Gateway  |
  | 4 | `/enrollment*`   | API Gateway  |
  | 5 | `/mock-idp*`     | API Gateway  (demo IdP only) |
  | — | Default `*`      | S3 (SPA)     |

  Drop `/mock-idp*` once you switch from the built-in demo IdP to real SAML.

> **`/healthz` is intentionally NOT routed to the API.** Through CloudFront it
> falls to the Default (SPA) behavior. To reach the health check via the
> CloudFront domain, add a dedicated `/healthz` → API Gateway behavior; otherwise
> curl the API Gateway URL directly (as in §8).

After changing behaviors, invalidate the distribution (`/*`) so the new routing
takes effect.

---

## 8. Verification (end-to-end)

Run these top to bottom. `<api-id>` is from §5.4; `<dist>` is your CloudFront
distribution domain from the frontend guide.

**1. Lambda is up (hit API Gateway directly):**
```bash
curl https://<api-id>.execute-api.us-west-2.amazonaws.com/healthz
# → {"status":"ok"}
```

**2. CloudFront → API Gateway origin works:**
```bash
curl -i https://<dist>.cloudfront.net/auth/session
# → HTTP/2 401, JSON body {"detail":"Not signed in"}
```
A 401 here is success — it proves CloudFront forwarded the request to the API and
the auth guard ran. (Note `/healthz` is *not* routed to the API through
CloudFront, so testing the health check via the CloudFront domain would return the
SPA instead — that's why step 1 hits API Gateway directly.)

**3. SPA deep links still work (served by S3, not a 404):**
```bash
curl -I https://<dist>.cloudfront.net/passport
# → 200, content-type: text/html   (SPA fallback via the spa-rewrite function)
```

**4. Real static files pass through:**
```bash
curl -I https://<dist>.cloudfront.net/assets/<hash>.js
# → 200 + long cache header
```

**5. Browser (use a phone-sized viewport — this UI is mobile-first):**
load the root → sign in via the mock IdP → land on `/home` → open `/passport`
(week tiles render) → do a manual or QR check-in (progress updates) →
hard-refresh the `/passport` deep link (still loads) → admin login →
ChallengeBuilder create/edit/reorder/publish all work.

**6. DynamoDB correctness / idempotency:**
- Create a challenge twice with the same name + semester → the uniqueness guard
  rejects the duplicate.
- Check in to the same task twice → the second call returns **409**
  (`DuplicateCheckIn`).
- Enroll in the same challenge twice → **idempotent** (no duplicate, no error).

**7. Regression net:**
```bash
make test-api     # still green (SQLAlchemy repo path)
```

---

## 9. Secrets & security

- **Use real, high-entropy secrets.** `WP_JWT_SECRET` and `WP_QR_SECRET` must be
  **32 bytes or longer**, random, and **stable across every invocation and
  deploy**. If the secret changes between requests, previously issued JWTs and QR
  tokens stop validating — users get logged out and QR check-ins fail. The
  defaults in `backend/app/config.py`
  (`"dev-only-change-me-please-set-a-real-32B+-secret"`) are for local dev only —
  never ship them.

  Generate strong values, e.g.:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

- **For the demo, SAM parameters are fine; for production, upgrade to a secrets
  store.** Passing secrets as SAM parameters puts them in the functions'
  environment (and in the CloudFormation stack). That's acceptable for a demo, but
  for production move them to **AWS Secrets Manager** or **SSM Parameter Store
  (SecureString)** and have the functions read them at cold start. This keeps the
  plaintext out of the template/stack and enables rotation and auditing.

- **The session cookie is `Secure` behind CloudFront HTTPS.** The `wp_session`
  cookie is set `HttpOnly`, `SameSite=Lax`, `Path=/`, and — on this deployment —
  `Secure=True`, because CloudFront terminates HTTPS and the whole app is served
  over TLS. Same-origin routing through the single CloudFront domain keeps
  `wp_session` a **first-party** cookie, which is why no CORS and no cross-site
  cookie settings are needed.

- **SAML (only if you enable a real IdP later).** A real IdP must reference the
  **CloudFront domain** for its ACS URL / entityID. The built-in mock IdP is
  same-origin, so it "just works" for the demo with `WP_AUTH_PROVIDER=mock`.

- **Per-function IAM is already least-privilege.** Each function is granted only
  the tables it uses (see §3.4) — `passport-fn` cannot write `Challenges`,
  `auth-fn` only touches `Students`. Keep it that way when editing the template.

---

## Appendix — command quick reference

```bash
# Prereqs (macOS)
brew install awscli aws-sam-cli
brew install --cask docker         # then start Docker Desktop
aws configure                      # region us-west-2

# Local test
make test-api                      # SQLite path stays green
docker run -d --name dynamodb-local -p 8000:8000 amazon/dynamodb-local
sam build
sam local start-api --env-vars env.local.json

# Deploy
sam build
sam deploy --guided                # first time (saves samconfig.toml)
sam deploy                          # thereafter
aws cloudformation describe-stacks \
  --stack-name shs-wellness-passport-backend \
  --region us-west-2 --query "Stacks[0].Outputs" --output table

# Seed (once, after first deploy)
python scripts/seed_dynamo.py

# Verify
curl https://<api-id>.execute-api.us-west-2.amazonaws.com/healthz
curl -i https://<dist>.cloudfront.net/auth/session
```

Then finish in [`docs/cloudfront-deploy-guide.md`](./cloudfront-deploy-guide.md)
(steps 5–6) to route CloudFront at this backend.
