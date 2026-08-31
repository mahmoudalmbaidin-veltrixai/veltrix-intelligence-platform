FROM python:3.12.13-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apk add --no-cache font-dejavu su-exec

RUN addgroup --system vip && adduser --system --ingroup vip --home /app vip

COPY pyproject.toml README.md requirements.runtime.lock ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN python -m pip install --no-cache-dir "pip==26.1.2" \
    && python -m pip install --no-cache-dir -r requirements.runtime.lock \
    && python -m pip install --no-cache-dir --no-deps . \
    && mkdir -p /data/vip-artifacts /data/vip-email-outbox /data/vip-pipeline-artifacts /data/vip-files \
    && chmod +x /app/scripts/docker-entrypoint.sh /app/scripts/demo-process-group.sh \
    && chown -R vip:vip /app /data

USER vip
EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
