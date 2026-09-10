# Container image for the LRTK API service.
# Multi-stage build keeps the final image small and runs as a non-root user.

FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LRTK_OUTPUT_DIR=/data/runs

# Non-root user and a writable data directory for run artifacts.
RUN groupadd --system lrtk \
    && useradd --system --gid lrtk --home-dir /app --shell /usr/sbin/nologin lrtk \
    && mkdir -p /data/runs \
    && chown -R lrtk:lrtk /data

COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=lrtk:lrtk examples ./examples
COPY --chown=lrtk:lrtk docs ./docs

USER lrtk
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

ENTRYPOINT ["lrtk"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
