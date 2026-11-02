# Propylon Shredder

Shredder is a custom Procrastinate worker service that converts PDF files to paginated HTML with
[pdf2htmlEX](https://github.com/pdf2htmlEX/pdf2htmlEX). It reads jobs from
PostgreSQL and POSTs a ZIP of the converted files to each job's callback URL.

**In the `backend/` folder:**

## Run with Docker

You need Docker, Docker Compose, and `make`. From this directory:

1. Copy `.env.example` to `.env` and set the PostgreSQL connection values. Replace
   the example password. The database must be reachable from the worker container;
   `127.0.0.1` refers to the container itself, not your host.
2. Install `uv` and create the Python environment (the Makefile's `env` target
   installs `uv` if needed):

   ```sh
   make env
   make build
   ```

3. Create a PostgreSQL database for Procrastinate, then apply its schema once:

   ```sh
   set -a
   . ./.env
   set +a
   uv run procrastinate --app shredder.app schema --apply
   ```

4. Start the worker and its Docker network:

   ```sh
   make docker
   ```

The worker listens to the queue set by `PROCRASTINATE_QUEUE`. Shredder does not
start PostgreSQL; provide a database separately and configure its connection in
`.env`.

## Queue a conversion

With the `.env` values exported as above, enqueue a job using Procrastinate's CLI:

```sh
uv run procrastinate --app shredder.app defer shredder.tasks.convert_pdf_to_html \
  '{"doc_path":"https://example.com/input.pdf","call_back_url":"https://example.com/shredder-result","doc_provider":"url","metadata":{"reference":"123"}}'
```

`doc_path` must be a URL the worker can GET. `doc_provider` currently supports
only `url`. You can optionally include `call_back_auth`, which is sent as the
callback's `Authorization` header, and `metadata`, which is returned as
additional form fields.

## Callback

After conversion, Shredder sends a multipart POST to `call_back_url`. It includes
the ZIP in the `file` field and form fields `job_id`, `doc_path`, and
`doc_provider`, plus any supplied metadata (with fields flattened). The ZIP contains the generated HTML
and related files.
NOTE: do not include field names in the input metadata JSON conflicting with 
`file`, `call_back_url`, `job_id`, `doc_path`, `doc_provider`.

## Configuration

Set values in `.env` for local Docker runs. The main settings are:

- `PROCRASTINATE_DB_HOST`, `PROCRASTINATE_DB_PORT`, `PROCRASTINATE_DB_NAME`,
  `PROCRASTINATE_DB_USER`, and `PROCRASTINATE_DB_PASSWORD`: PostgreSQL connection.
- `PROCRASTINATE_QUEUE`: queue to consume (default: `shredder_queue`).
- `PROCRASTINATE_CONCURRENCY`: number of jobs processed concurrently (default: `4`).
- `PROCRASTINATE_MAX_JOB_TTL`: maximum job runtime in seconds (default: `600`).
- `SHREDDER_CONVERSION_CONFIG`: optional comma-separated pdf2htmlEX arguments.

See `.env.example` for the full set of build and worker settings. Do not commit
credentials.

## Development

The project requires Python 3.13.11. Install the development dependencies with:

```sh
make env
make build
```

Tests:

- `make test` runs the functional tests. They mock HTTP and `pdf2htmlEX`, so no
  database or container is needed.
- `make test-integration` starts the worker container, queues a real job, and checks
  the callback. It needs the database from `.env` reachable on `127.0.0.1` (override
  with `TEST_PROCRASTINATE_DB_HOST`/`TEST_PROCRASTINATE_DB_PORT`). The test starts a
  mock server on port 1234 that serves `example.pdf` and receives the callback; the
  worker reaches it through `host.docker.internal`.
- `make test-suite` runs both.
