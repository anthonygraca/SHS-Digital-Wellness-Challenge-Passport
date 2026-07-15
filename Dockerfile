# syntax=docker/dockerfile:1
#
# One image, one origin. The SPA is built here and served by the same FastAPI
# process that serves the API, because the app requires them to share an origin:
# the session cookie is HttpOnly/SameSite=Lax and every client call uses a
# relative path. Splitting them across two containers or two ports drops the
# cookie and breaks sign-in.

# ---- stage 1: build the SPA -------------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /frontend

# package.json + lockfile first: this layer caches until dependencies change, so
# editing source does not re-run npm ci.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# VITE_API_BASE is intentionally left unset. It is baked in at build time, and
# empty means "same origin, relative paths" — which is what this image serves.
RUN npm run build

# ---- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

# Matches CI (.github/workflows/ci.yml runs the backend suite on 3.12). pyproject
# declares >=3.9 as the floor, but 3.12 is the version actually tested.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The app is run from source rather than pip-installed, mirroring the local
# `uvicorn app.main:app` invocation. uvicorn puts its --app-dir (default ".") on
# sys.path, so `app.main` resolves against this WORKDIR.
COPY backend/app ./app

# Served by the SpaStaticFiles mount in app/main.py.
COPY --from=frontend /frontend/dist ./app/static

# SQLite lives outside the image so a redeploy does not wipe it. The default in
# config.py is a *relative* path (sqlite:///./wellness_passport.db) that would
# land in WORKDIR and die with the container; this points it at a mountable
# volume instead. Note the four slashes — sqlite:////data/x.db is an absolute path.
RUN mkdir -p /data
ENV WP_DATABASE_URL="sqlite:////data/wellness_passport.db"
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

# No --reload: that is a dev-only flag. Single worker keeps SQLite writes serialized.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
