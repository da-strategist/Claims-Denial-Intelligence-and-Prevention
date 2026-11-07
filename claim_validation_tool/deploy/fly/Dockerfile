# API image for the hosted demo. Built by deploy/fly/deploy.sh from a staged context
# (the API code, the synthetic data and a seed of orgs/ and users.json), never the whole repo.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.12 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Same layout as the repository, so the default paths (Data/raw_data) resolve
COPY Data/raw_data Data/raw_data
COPY claim_validation_tool/backend/app claim_validation_tool/backend/app
COPY seed /seed
COPY entrypoint.sh /entrypoint.sh

# Everything the API writes goes to the volume mounted at /data
ENV RCM_ORGS_DIR=/data/orgs \
    RCM_USERS_FILE=/data/users.json \
    RCM_AUDIT_FILE=/data/logs/audit.jsonl \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app/claim_validation_tool/backend
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
