"""
Integration tests for the shredder application.

Requires the shredder worker container and its Procrastinate database to be running.
`make test-integration` starts the container. The test starts the mock server in a background
thread and reads the callbacks it receives directly from memory.

Optional environment overrides:
- MOCK_SERVER_PORT: mock server port (default 1234).
- MOCK_SERVER_CALLBACK_HOST: hostname the worker container uses to reach the mock server
  (default host.docker.internal).
- TEST_PROCRASTINATE_DB_HOST / TEST_PROCRASTINATE_DB_PORT: database address as seen from the
  machine running the tests (default 127.0.0.1 / PROCRASTINATE_DB_PORT).
- MOCK_SERVER_STARTUP_DELAY: seconds to wait after starting the mock server, because Docker
  Desktop takes a moment to forward a newly opened host port into containers (default 2).
- INTEGRATION_TIMEOUT: seconds to wait for the callback (default 120).
"""

import asyncio
import io
import os
import threading
import time
import zipfile

import procrastinate
import pytest
from procrastinate.jobs import Status
from psycopg.conninfo import make_conninfo

from tests.mock_server import MockServer

MOCK_SERVER_PORT = int(os.getenv("MOCK_SERVER_PORT", "1234"))
CALLBACK_HOST = os.getenv("MOCK_SERVER_CALLBACK_HOST", "host.docker.internal")
TIMEOUT = float(os.getenv("INTEGRATION_TIMEOUT", "5"))
STARTUP_DELAY = float(os.getenv("MOCK_SERVER_STARTUP_DELAY", "2"))
WORKER_URL = f"http://{CALLBACK_HOST}:{MOCK_SERVER_PORT}"
TASK_NAME = "shredder.tasks.convert_pdf_to_html"
FAILED_STATUSES = {Status.FAILED, Status.CANCELLED, Status.ABORTED}


@pytest.fixture(scope="module")
def mock_server():
    """Start the mock server in a background thread."""
    server = MockServer(MOCK_SERVER_PORT)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(STARTUP_DELAY)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
async def procrastinate_app():
    """Add an actual job to the procrastinate worker queue for testing."""
    connector = procrastinate.PsycopgConnector(
        conninfo=make_conninfo(
            host=os.getenv("TEST_PROCRASTINATE_DB_HOST", "127.0.0.1"),
            port=os.getenv("TEST_PROCRASTINATE_DB_PORT", os.environ["PROCRASTINATE_DB_PORT"]),
            user=os.environ["PROCRASTINATE_DB_USER"],
            password=os.environ["PROCRASTINATE_DB_PASSWORD"],
            dbname=os.environ["PROCRASTINATE_DB_NAME"],
        )
    )
    app = procrastinate.App(connector=connector)
    async with app.open_async():
        yield app


async def _wait_for_callback(
    app: procrastinate.App,
    server: MockServer,
    job_id: int,
    *,
    callback_auth: str,
    expected_fields: dict,
) -> None:
    """Wait for the job's callback to reach the mock server, then validate it."""
    received = None
    deadline = time.monotonic() + TIMEOUT
    while received is None and time.monotonic() < deadline:
        # Wait in 1s steps on a worker thread so the event loop stays free and a failed
        # job is reported straight away.
        received = await asyncio.to_thread(server.wait_for_callback, str(job_id), 1)
        if received is None:
            status = await app.job_manager.get_job_status_async(job_id)
            if status in FAILED_STATUSES:
                pytest.fail(f"Job {job_id} ended with status {status.value}; see worker logs.")
    if received is None:
        pytest.fail(f"No callback received for job {job_id} within {TIMEOUT}s.")

    assert received["authorization"] == callback_auth
    assert received["fields"] == {"job_id": str(job_id), **expected_fields}
    upload = received["files"]["file"]
    assert upload["filename"] == f"{job_id}.zip"
    assert zipfile.is_zipfile(io.BytesIO(upload["content"]))
    with zipfile.ZipFile(io.BytesIO(upload["content"])) as archive:
        html_files = [n for n in archive.namelist() if n.endswith(".html")]
        assert len(html_files) == 1
        html = archive.read(html_files[0])
        assert b"pdf2htmlEX" in html
        assert b"page-container" in html


async def test_integration_conversion(procrastinate_app, mock_server):
    """Queue a real job and check the worker POSTs the converted zip back to the mock server."""
    doc_path = f"{WORKER_URL}/example.pdf"
    callback_auth = "Bearer integration-test-token"
    metadata = {"reference": "integration-test"}

    job_id = await procrastinate_app.configure_task(
        name=TASK_NAME, queue=os.getenv("PROCRASTINATE_QUEUE", "shredder_queue")
    ).defer_async(
        doc_path=doc_path,
        call_back_url=f"{WORKER_URL}/webhook",
        call_back_auth=callback_auth,
        doc_provider="url",
        metadata=metadata,
    )

    await _wait_for_callback(
        procrastinate_app,
        mock_server,
        job_id,
        callback_auth=callback_auth,
        expected_fields={"doc_path": doc_path, "doc_provider": "url", **metadata},
    )
