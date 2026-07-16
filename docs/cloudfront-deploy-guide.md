# Deploy the SPA to S3 + CloudFront (Console click-through)

A beginner-friendly, step-by-step guide to putting the React/Vite frontend online.

You will deploy the built SPA (from `frontend/dist/`) to a **new private S3 bucket**
(`shs-wellness-passport-frontend`) and serve it through **one CloudFront distribution**.
That same distribution also forwards API paths to an **API Gateway** origin, so the browser
only ever talks to a single domain. This keeps everything **same-origin** — no CORS, no
changes to any frontend URLs, and the session cookie keeps working.

This is a pure **AWS Console** walkthrough. It assumes you have an AWS account and can sign
in, but have never used S3 or CloudFront before. Every screen tells you *what to click*,
*what to type*, and *why*.

> Region note: this guide uses **`us-west-2`** in every example, but **any region works** —
> just use the same region consistently. CloudFront itself is global; the region only affects
> where the S3 bucket lives.

> The AWS Console wording changes often. Button and field labels here match the Console at the
> time of writing; if a label is slightly different, look for the closest match — the concepts
> below don't change.

---

## How it fits together

There is **one CloudFront domain** in front of two back-ends:

- **S3** holds the static SPA files (HTML, JS, CSS, the PWA service worker).
- **API Gateway** is the real server (Lambda behind it) for auth and data calls.

CloudFront decides where each request goes using an ordered list of **behaviors** (path-pattern
rules). The first rule that matches a request wins. API paths (`/api/*`, `/auth/*`,
`/enrollment*`, `/mock-idp*`) go to API Gateway; everything else falls through to S3 and is
served as the SPA.

```
  Browser ──HTTPS──▶  CloudFront (one domain, valid cert)
                        │
      ┌─────────────────┼──────────────────────────────┐
      │ behaviors (first match wins, top→bottom):       │
      │  /auth/callback → S3   (SPA route)              │
      │  /api/*         → API Gateway                   │
      │  /auth/*        → API Gateway                   │
      │  /enrollment*   → API Gateway                   │
      │  /mock-idp*     → API Gateway  (demo IdP only)  │
      │  Default *      → S3   (SPA + spa-rewrite fn)   │
      └───────┬──────────────────────┬──────────────────┘
        S3 (private, OAC)      API Gateway (HTTP API, $default stage, HTTPS)
        SPA static files              │  routes fan out by path to Lambda
```

**Why same-origin matters.** Every API call in the app is a *relative* path (`/api/...`,
`/auth/...`, `/enrollment`) and login relies on a session cookie. Because the browser only ever
sees the single CloudFront domain, those relative paths resolve to the same origin, the cookie
stays first-party, and the backend needs **no CORS** configuration. You do **not** edit any
frontend code to deploy — the same relative paths that work in local dev work in production.

### Two meanings of "default" (don't mix them up)

- **CloudFront Default (`*`) behavior** — the catch-all rule, always evaluated **last**. It
  serves the SPA from S3 for any path the specific rules didn't match. Every distribution has
  exactly one.
- **API Gateway `$default` stage** — the API Gateway stage whose URL has *no* stage-name path
  segment, so `/api/passport` passes through unchanged. This comes from the backend deploy
  (Workstream 2); you just point CloudFront at its domain.

They are unrelated things that happen to share the word "default."

---

## Prerequisites

- An AWS account, and a sign-in with permission to use **S3** and **CloudFront**.
- **Node** installed locally (already set up in this repo) so you can run the build.
- The **API Gateway endpoint** from the backend deploy, which looks like
  `{apiId}.execute-api.us-west-2.amazonaws.com`. You only need this for Steps 5–6 (the API
  behaviors). You can do the S3/CloudFront steps (0–4) first and come back once the endpoint
  exists.

---

## Step 0 — Build the SPA

Produce the static files CloudFront will serve. From the repo root:

```bash
make build
```

This runs the production Vite build (`cd frontend && npm run build`) and writes the output to
**`frontend/dist/`**. When it finishes, that folder contains:

```
frontend/dist/
├── index.html               ← the SPA shell (entry point)
├── manifest.webmanifest     ← PWA manifest
├── registerSW.js            ← registers the service worker
├── sw.js                    ← the PWA service worker
├── workbox-*.js             ← service-worker runtime
└── assets/                  ← hashed JS/CSS bundles (e.g. index-a1b2c3.js)
```

You will upload the **contents** of this folder (not the folder itself) to the bucket.

---

## Step 1 — Create the private S3 bucket

S3 is where the static files live. You want a **private** bucket: the public should reach the
files only *through CloudFront*, never by hitting S3 directly.

1. In the AWS Console, open the **S3** service. (Type "S3" in the top search bar.)
2. Confirm the region shown in the top-right corner is **US West (Oregon) `us-west-2`** (or your
   chosen region). *Why:* the bucket is created in whatever region is selected.
3. Click **Create bucket**.
4. **Bucket name:** `shs-wellness-passport-frontend`. *Why:* bucket names are globally unique
   across all of AWS; if it's taken, add a short suffix and use that name everywhere below.
5. **AWS Region:** leave it as `us-west-2` (or your region).
6. **Block Public Access settings for this bucket:** leave **Block *all* public access ON**
   (all four checkboxes checked). *Why:* the bucket stays completely private. CloudFront will be
   granted read access later through a mechanism called Origin Access Control (OAC), so the
   files are never publicly reachable from S3. **Do not** enable "Static website hosting" — we
   are not using S3's website endpoint at all; CloudFront serves the files.
7. Leave the rest at defaults (versioning off is fine; default encryption on is fine).
8. Click **Create bucket**.

You now have an empty, private bucket.

---

## Step 2 — Upload the built files

Upload the **contents of `frontend/dist/`** into the **root** of the bucket. The `index.html`
must sit at the top level of the bucket (`s3://shs-wellness-passport-frontend/index.html`), not
inside a `dist/` sub-folder.

1. Open your new bucket, then click **Upload**.
2. Click **Add files** and select every file at the top of `frontend/dist/` (`index.html`,
   `manifest.webmanifest`, `registerSW.js`, `sw.js`, `workbox-*.js`).
3. Click **Add folder** and select the `assets/` folder so its files upload under an `assets/`
   prefix. *Why:* the app references `/assets/...`, so those files must keep that path.
4. Click **Upload** and wait for it to finish. When done, the bucket root should show
   `index.html`, the other top-level files, and an `assets/` folder.

*(Optional) Cache headers.* You can set object metadata to control browser/CloudFront caching:

| File(s) | Suggested `Cache-Control` | Why |
|---|---|---|
| `assets/*` | `public,max-age=31536000,immutable` | Hashed filenames change on every build, so they can cache forever. |
| `index.html`, `sw.js`, `registerSW.js`, `manifest.webmanifest` | `no-cache` | These keep the same name across builds, so they must be re-checked. |

To set these, select the files and use **Actions → Edit metadata** (or set them at upload time
under **Properties → Metadata**). If you skip this, that's fine — you'll rely on the CloudFront
invalidation in Step 7 to push updates instead.

---

## Step 3 — Create the CloudFront distribution (with OAC)

CloudFront is the single public domain in front of everything. In this step you create the
distribution, connect it to the S3 bucket privately using **Origin Access Control (OAC)**, and
tell it to serve `index.html` at the root.

1. Open the **CloudFront** service in the Console. (CloudFront is global — no region selector.)
2. Click **Create distribution**.
3. **Origin domain:** click the field and pick your bucket
   `shs-wellness-passport-frontend.s3.us-west-2.amazonaws.com` from the dropdown. *Why:* this is
   the S3 source of the static files.
4. **Origin access:** choose **Origin access control settings (recommended)**. Click **Create
   control setting**, accept the defaults in the dialog, and **Create**. *Why:* OAC lets *only
   this distribution* read the private bucket; the public cannot reach S3 directly. Keep the new
   OAC selected.
5. **Viewer protocol policy:** choose **Redirect HTTP to HTTPS**. *Why:* forces all traffic onto
   HTTPS, which the session cookie (marked `Secure`) requires.
6. **Cache policy** (for this default S3 behavior): choose **CachingOptimized**. *Why:* good
   defaults for static assets.
7. **Web Application Firewall (WAF):** you can disable it for now (it costs extra). Your choice.
8. **Default root object:** type **`index.html`**. *Why:* when someone visits the bare domain
   (`/`), CloudFront serves `index.html` — the SPA shell.
9. Leave other settings at defaults and click **Create distribution**.
10. Wait for **Last modified / Status** to finish deploying (a few minutes). Note the
    distribution's domain name — it looks like **`dXXXXXXXX.cloudfront.net`**. That is your one
    public URL.

**Paste the generated bucket policy.** After creating the distribution with OAC, CloudFront
shows a banner/button offering the **S3 bucket policy** it needs. Copy that policy, then:

1. Go to **S3 → your bucket → Permissions → Bucket policy → Edit**.
2. Paste the policy and **Save changes**.

*Why:* this policy grants `s3:GetObject` **only** to this CloudFront distribution (scoped by its
ARN). Public access stays fully blocked; CloudFront becomes the sole reader. The policy AWS
generates looks like this (your account ID and distribution ID fill in the placeholders):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontServicePrincipalReadOnly",
      "Effect": "Allow",
      "Principal": { "Service": "cloudfront.amazonaws.com" },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::shs-wellness-passport-frontend/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::{accountId}:distribution/{distributionId}"
        }
      }
    }
  ]
}
```

At this point, visiting `https://dXXXXXXXX.cloudfront.net/` should load the app's home screen.
Deep links like `/passport` will still 404 until the next step.

---

## Step 4 — The `spa-rewrite` CloudFront Function

A single-page app has client-side routes (`/passport`, `/home`, `/auth/callback`) that are
**not** real files in S3. If someone refreshes `/passport`, S3 has no `/passport` object and
returns an error. The fix is a tiny **CloudFront Function** that rewrites any *extensionless*
request to `/index.html`, so the SPA shell loads and React Router takes over.

1. In CloudFront, open **Functions** (left nav) → **Create function**.
2. **Name:** `spa-rewrite`. Click **Create function**.
3. In the **Build** tab, replace the code with **exactly** this:

   ```js
   function handler(event) {
     var request = event.request, uri = request.uri;
     var last = uri.substring(uri.lastIndexOf('/') + 1);
     if (last.indexOf('.') === -1) { request.uri = '/index.html'; } // extensionless → SPA shell
     return request;
   }
   ```

   *Why:* if the last path segment has no dot (no file extension), it's a client-side route, so
   we serve the SPA shell. Requests for real files (`/assets/index-a1b2c3.js`, `/sw.js`) contain
   a dot and pass through untouched.
4. Click **Save changes**, then the **Publish** tab → **Publish function**. *Why:* only a
   published function can be attached to a distribution.
5. Attach it to the **two behaviors that serve S3** — the **Default (`*`)** behavior and the
   **`/auth/callback`** behavior (you'll create `/auth/callback` in Step 6). For each: open the
   behavior, scroll to **Function associations → Viewer request**, choose **CloudFront Function**
   and select **`spa-rewrite`**, then save. *Why:* SPA fallback should apply only where S3 is the
   origin. It must **not** run on API behaviors — those go to API Gateway and must never be
   rewritten to `index.html`.

> ⚠️ **Do NOT add CloudFront "Custom error responses" (e.g. 403/404 → `/index.html`, 200).**
> That is the common tutorial trick for SPA routing, but custom error responses are
> **distribution-wide** — they apply to *every* origin, including API Gateway. A real API 404 (or
> 403) would get rewritten into `index.html` with a 200 status, so the frontend's `res.ok` check
> passes and then `res.json()` chokes on HTML. This is exactly the failure documented at
> `frontend/vite.config.ts:37-41`. The `spa-rewrite` function handles SPA fallback on the S3
> behaviors only, without ever touching API responses. Use the function; skip custom error
> responses.

---

## Step 5 — Add API Gateway as a second origin

Now give CloudFront a second place to send traffic: the API Gateway endpoint from the backend
deploy. (Do this once that endpoint exists.)

1. Open your distribution → **Origins** tab → **Create origin**.
2. **Origin domain:** paste the API Gateway host, **without** `https://` and **without** any
   path — just the hostname: `{apiId}.execute-api.us-west-2.amazonaws.com`.
3. **Protocol:** choose **HTTPS only**, and set **HTTPS port** to **443**. *Why:* API Gateway
   serves HTTPS with a valid managed certificate, so CloudFront can use it as a secure origin
   with no self-signed-cert problems.
4. **Origin path:** leave **empty**. *Why:* the API uses the `$default` stage (no stage segment
   in the URL), so `/api/passport` must reach API Gateway as `/api/passport` unchanged.
5. Leave other settings at defaults and **Create origin**.

You now have two origins: the S3 bucket and the API Gateway host.

---

## Step 6 — Create the API behaviors (order matters)

Behaviors are matched **top to bottom, first match wins**. You'll add rules that send API paths
to the API Gateway origin, plus one SPA route (`/auth/callback`) that must be caught *before*
the general `/auth/*` rule. Create them in this exact order:

| # | Path pattern     | Origin       | Cache policy      | Origin request policy         | Function      |
|---|------------------|--------------|-------------------|-------------------------------|---------------|
| 1 | `/auth/callback` | S3           | CachingOptimized  | —                             | `spa-rewrite` |
| 2 | `/api/*`         | API Gateway  | CachingDisabled   | AllViewerExceptHostHeader     | —             |
| 3 | `/auth/*`        | API Gateway  | CachingDisabled   | AllViewerExceptHostHeader     | —             |
| 4 | `/enrollment*`   | API Gateway  | CachingDisabled   | AllViewerExceptHostHeader     | —             |
| 5 | `/mock-idp*`     | API Gateway  | CachingDisabled   | AllViewerExceptHostHeader     | —             |
| — | Default `*`      | S3           | CachingOptimized  | —                             | `spa-rewrite` |

For each row, open **Behaviors → Create behavior** and fill in:

- **Path pattern:** the value from the table.
- **Origin:** the S3 bucket or the API Gateway origin, as shown.
- **Viewer protocol policy:** **Redirect HTTP to HTTPS** (same as the default).
- **Cache policy:** as shown. Use **CachingDisabled** on every API behavior. *Why:* API
  responses are per-user and must never be cached.
- **Origin request policy** (API behaviors only): **AllViewerExceptHostHeader**. *Why:* API
  Gateway rejects a request that forwards CloudFront's `Host` header (Host mismatch → 403).
  `AllViewerExceptHostHeader` forwards everything **except** the Host header — crucially it still
  forwards **cookies and query strings**, which auth needs. Do **not** use plain `AllViewer`.
- **Allowed HTTP methods** (API behaviors): choose the set that includes
  **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**. *Why:* the API uses POST/PATCH/DELETE (login,
  check-in, challenge edits), not just reads.
- **Function associations → Viewer request** (S3 behaviors only, i.e. `/auth/callback` and the
  Default): **`spa-rewrite`**. Leave API behaviors with no function.

**Why `/auth/callback` comes first (row 1).** `/auth/callback` is a **client-side SPA route**,
not a backend endpoint — it's where the browser lands after login. It must be caught by the S3
behavior *before* the `/auth/*` rule (row 3) would send it to API Gateway. First-match-wins is
why order matters: put the specific `/auth/callback` above the general `/auth/*`.

**Note on `/mock-idp*` (row 5).** This routes the built-in **demo** identity provider to the
backend. It is only needed while using the mock IdP for demos; drop this behavior if you switch
to a real SAML provider.

The **Default (`*`)** behavior already exists from Step 3 (S3 + CachingOptimized + `spa-rewrite`).
Just confirm the `spa-rewrite` function is attached to it (Step 4).

> **`/healthz` is intentionally *not* routed to the API.** There is no `/healthz` behavior, so
> through CloudFront it falls to the Default rule and returns the SPA, not the health JSON. That's
> fine — the SPA never calls `/healthz`. To reach the health check, curl the API Gateway URL
> directly, or add a dedicated `/healthz → API Gateway` behavior if you specifically want it on
> the CloudFront domain.

After saving the behaviors, wait for the distribution to finish deploying.

---

## Aside — small recommended `vite.config.ts` change (handled separately)

This is a **one-line frontend code change**, independent of CloudFront and handled on its own —
listed here only so you know it exists. The PWA service worker's navigation fallback can serve
the cached app shell for full-page navigations to backend paths (`/auth/login`,
`/mock-idp/login`). Adding a Workbox `navigateFallbackDenylist` tells the service worker to let
those hit the network (and thus the API) instead:

```ts
VitePWA({ registerType: "autoUpdate",
  workbox: { navigateFallbackDenylist: [/^\/auth/, /^\/api/, /^\/enrollment/, /^\/mock-idp/] },
  manifest: { /* unchanged */ } })
```

This is a latent single-origin issue, not a CloudFront requirement. It does not change any of
the Console steps above.

---

## Verify it works

Replace `dXXXXXXXX.cloudfront.net` with your real distribution domain. Run these from a terminal.

1. **API reaches the backend through CloudFront** — session check returns a JSON 401:

   ```bash
   curl -i https://dXXXXXXXX.cloudfront.net/auth/session
   ```

   Expect **`HTTP/2 401`** and a JSON body `{"detail":"Not signed in"}`. This proves the
   CloudFront → API Gateway origin and the `/auth/*` behavior work. *(If this returned HTML
   instead, the request fell through to the SPA — recheck the `/auth/*` behavior and its order.)*

   > Remember `/healthz` is **not** routed to the API, so
   > `curl https://dXXXXXXXX.cloudfront.net/healthz` returns the SPA, not health JSON. That's
   > expected. Curl the API Gateway URL directly for the health check, or add a `/healthz` behavior.

2. **SPA deep-link fallback** — a client route returns the app shell, not a 404:

   ```bash
   curl -I https://dXXXXXXXX.cloudfront.net/passport
   ```

   Expect **`HTTP/2 200`** with `content-type: text/html`. This proves the `spa-rewrite` function
   is rewriting extensionless paths to `index.html`.

3. **Real static file passthrough** — a hashed asset serves directly with a long cache:

   ```bash
   curl -I https://dXXXXXXXX.cloudfront.net/assets/<hash>.js
   ```

   (Use a real filename from your `frontend/dist/assets/` folder.) Expect **`HTTP/2 200`** and a
   long `cache-control`. This proves files with an extension bypass the SPA rewrite.

4. **Browser end-to-end (use a phone-sized viewport — this UI is mobile-first):**
   - Open `https://dXXXXXXXX.cloudfront.net/` → the home screen loads.
   - Sign in via the mock IdP → you're redirected back to `/auth/callback` → land signed in.
   - Open `/passport` → it loads and shows the challenge/week tiles.
   - Do a manual or QR check-in → progress updates.
   - **Hard-refresh the `/passport` deep link** → it still loads (SPA fallback), not a 404.

If all four pass, the deployment is working: one domain, same-origin, no CORS.

---

## Redeploying later

Whenever the frontend changes, you rebuild, re-upload, and tell CloudFront to drop its cached
copies so users get the new files:

1. **Build:** `make build` (regenerates `frontend/dist/`).
2. **Sync to S3** — upload changed files and delete removed ones:

   ```bash
   aws s3 sync frontend/dist s3://shs-wellness-passport-frontend --delete
   ```

   *Why `--delete`:* removes stale old hashed asset files from the bucket so it mirrors `dist/`.
3. **Invalidate the CloudFront cache** so viewers fetch the new files immediately:

   ```bash
   aws cloudfront create-invalidation --distribution-id <YOUR_DIST_ID> --paths "/*"
   ```

   *Why:* CloudFront caches files at edge locations; invalidating `/*` clears them all. The first
   **1,000 invalidation paths per month are free**, and `/*` counts as one path.

### Optional helper: `scripts/deploy-frontend.sh`

You can wrap the three redeploy steps in a small script so a deploy is one command. The optional
`scripts/deploy-frontend.sh` helper does exactly:

```bash
make build
aws s3 sync frontend/dist s3://shs-wellness-passport-frontend --delete
aws cloudfront create-invalidation --distribution-id <YOUR_DIST_ID> --paths "/*"
```

That script ships in the repo — run it instead of doing the steps by hand:

```bash
scripts/deploy-frontend.sh shs-wellness-passport-frontend <YOUR_DIST_ID>
```

---

## Quick reference

| Thing | Value / placeholder |
|---|---|
| S3 bucket | `shs-wellness-passport-frontend` (private, Block Public Access ON) |
| Region (example) | `us-west-2` (any region works) |
| CloudFront domain | `dXXXXXXXX.cloudfront.net` |
| API Gateway origin | `{apiId}.execute-api.us-west-2.amazonaws.com` (HTTPS only, port 443) |
| Default root object | `index.html` |
| CloudFront Function | `spa-rewrite` (viewer request; on the two S3 behaviors only) |
| API behavior cache policy | `CachingDisabled` |
| API behavior origin request policy | `AllViewerExceptHostHeader` (never plain `AllViewer`) |
| Do NOT | add custom error responses (403/404 → index.html) |
