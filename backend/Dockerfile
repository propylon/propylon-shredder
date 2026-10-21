ARG base_version=pdf2htmlex/pdf2htmlex:0.18.8.rc2-master-20200820-alpine-3.12.0-x86_64
FROM ${base_version}

COPY .env ./apps/
COPY pyproject.toml ./apps/
COPY uv.lock ./apps/
COPY ./etc ./apps/
COPY ./apps/shredder/src/shredder ./apps/shredder

RUN apt-get update && apt-get --no-install-recommends install -y \
    postgresql-client \
    curl \
    ttfautohint \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    addgroup --gid 1000 appgroup && adduser --uid 1000 --system --gid 1000  appuser

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
	~/.local/bin/uv venv --allow-existing --python $(PYTHON_VERSION) $(ENV_DIR)

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ENV PATH="/.venv/bin:$PATH"
RUN uv sync --locked

# Set exec permission for the startup scripts.
RUN find /apps/etc -name '*.sh' -exec chmod +x {} +

CMD ["bash", "-c", "exec /apps/etc/run_server.sh"]
