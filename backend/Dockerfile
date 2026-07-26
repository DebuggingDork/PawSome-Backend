# syntax=docker/dockerfile:1

# uv's own image: Python 3.12 with uv already on PATH, so there's no pip
# bootstrap step and the lockfile is installed exactly as resolved locally.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies before source, so editing a route doesn't reinstall asyncpg.
# --frozen fails the build if uv.lock disagrees with pyproject.toml rather than
# silently resolving something different from what was tested locally.
# --no-install-project: this project has no [build-system], so uv treats it as
# virtual and we run it from the working directory instead of site-packages.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Render injects PORT and routes to whatever the container listens on. The
# default is only for running this image locally.
ENV PORT=8000
EXPOSE 8000

# Drop privileges. Nothing here writes to disk at runtime -- uploads go to R2 --
# so the app does not need to own /app.
RUN useradd --create-home --uid 10001 pawsome
USER pawsome

# Migrations run on boot because Render's pre-deploy hook is a paid feature.
# `exec` hands PID 1 to uvicorn so SIGTERM reaches it and deploys drain
# cleanly instead of being killed after the grace period.
#
# This assumes ONE web instance. If you ever scale past a single instance,
# move `alembic upgrade head` to a pre-deploy command -- concurrent boots
# racing on the same migration is a bad time.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
