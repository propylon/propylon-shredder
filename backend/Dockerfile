# TODO: Make the first stage more dynamic
# Currently python version is hard-coded

ARG base_image=pdf2htmlex/pdf2htmlex:0.18.8.rc2-master-20200820-alpine-3.12.0-x86_64
# ARG PYTHON_BUILD_STANDALONE_VERSION=20250115
# ARG PYTHON_VERSION_MINOR=3.13.1

# #################################################################################################
# Stage 1: Build Image - Grab a prebuilt, portable Python 3.13 (musl/Alpine-compatible)
FROM ${base_image} AS buid-image
# FROM --platform=$BUILDPLATFORM alpine:3.20 AS buid-image

# Download Python
ARG PYTHON_VERSION
RUN echo "PYTHON VERSION ${PYTHON_VERSION:?PYTHON_VERSION must be set}"
ARG PYTHON_BUILD_LIST_URL=https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest

RUN apk update
RUN apk add --no-cache curl
RUN apk add --no-cache jq

RUN DOWNLOAD_URL=$(curl -sSL "$PYTHON_BUILD_LIST_URL" | \
    jq -r '.assets[] | select(.name | contains("cpython-'"$PYTHON_VERSION"'") and contains("x86_64-unknown-linux-musl-install_only_stripped")) | .browser_download_url') \
    && curl -sSL $DOWNLOAD_URL -o /tmp/python.tar.gz

# RUN curl -L -o /tmp/python.tar.gz "$DOWNLOAD_URL" \
#    "https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_BUILD_STANDALONE_VERSION}/cpython-${PYTHON_VERSION_MINOR}+${PYTHON_BUILD_STANDALONE_VERSION}-x86_64-unknown-linux-musl-install_only.tar.gz" \
RUN mkdir -p /opt/python \
 && tar -xzf /tmp/python.tar.gz -C /opt/python --strip-components=1

# #################################################################################################
# Stage 2: Service Image
FROM ${base_image} AS service-image

# Copy the APK package registry to avoid re-running apk update
COPY --from=buid-image /var/cache/apk/ /var/cache/apk/

# Copy the Python installation
ARG PYTHON_VERSION
COPY --from=buid-image /opt/python /opt/python
ENV PATH="/opt/python/bin:${PATH}"
RUN ln -sf /opt/python/bin/python$PYTHON_VERSION /usr/local/bin/python3 \
 && ln -sf /opt/python/bin/python$PYTHON_VERSION /usr/local/bin/python
# Validate python
RUN python3 --version

# For Procrastinate PG Connector - ctypes.find_library needs libpq's linker files and binutils on musl.
RUN apk add --no-cache postgresql-dev binutils

COPY .env /propylon/
COPY pyproject.toml /propylon/
COPY uv.lock /propylon/
COPY ./etc /propylon/etc/
COPY ./shredder/src /propylon/shredder/src/

RUN chmod +x /propylon/etc/run_server.sh
RUN set -o allexport && source /propylon/.env && set +o allexport

# RUN apk update
# RUN apk add --no-cache python3 py3-pip python3-dev build-base
# RUN apk add --no-cache python3
# RUN apk add --no-cache postgresql-client
# RUN apk add --no-cache curl

# Recommended by PDF2HTMLEX to get better results. Add to subprocess calls
# RUN apk add ttfautohint && \

# RUN addgroup --gid 1000 appgroup && adduser --uid 1000 --system --gid 1000  appuser

#RUN curl -LsSf https://astral.sh/uv/install.sh | sh
#RUN /root/.local/bin/uv venv --allow-existing --python "${PYTHON_VERSION:?PYTHON_VERSION must be set}" /.venv
RUN pip install uv
RUN uv venv --allow-existing --python "$PYTHON_VERSION" /propylon/.venv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
ENV PATH="/propylon/.venv/bin:$PATH"

WORKDIR /propylon/
RUN uv sync --locked --no-dev

# Set exec permission for the startup scripts.
# RUN find /propylon/etc -name '*.sh' -exec chmod +x {} +

# Override the original base image entrypoint
ENTRYPOINT []
CMD ["/bin/sh", "-c", "exec /propylon/etc/run_server.sh"]
