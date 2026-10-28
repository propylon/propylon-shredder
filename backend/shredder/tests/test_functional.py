"""Functional tests for the shredder application. No database, network, or worker required."""

import asyncio
import io
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from shredder.tasks import ConversionError, convert_pdf_to_html, zip_directory
from shredder.utils import set_timeout
from tests.mock_server import parse_multipart

TIMEOUT_SECONDS = 0.1
MAX_EXPECTED_SECONDS = 1
EXAMPLE_PDF = Path(__file__).parent / "static" / "example.pdf"
PDF2HTMLEX = Path("/usr/local/bin/pdf2htmlEX")
DOC_URL = "http://docs.example/example.pdf"
CALLBACK_URL = "http://callback.example/webhook"
CALLBACK_AUTH = "Bearer test-token"


@set_timeout(TIMEOUT_SECONDS)
async def slow_task():
    await asyncio.sleep(2)


@set_timeout(1)
async def fast_task():
    return "done"


async def test_functional_set_timeout():
    """A task that exceeds its timeout is cancelled with a TimeoutError."""
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        await slow_task()
    elapsed = time.monotonic() - start
    assert TIMEOUT_SECONDS <= elapsed < MAX_EXPECTED_SECONDS


async def test_functional_set_timeout_returns_result():
    assert await fast_task() == "done"


def _job_context(job_id=42):
    return SimpleNamespace(job=SimpleNamespace(id=job_id))


def _fake_pdf2htmlex(returncode=0):
    """Stand-in for pdf2htmlEX: checks its input and writes HTML into --dest-dir."""
    calls = []

    async def fake_exec(*command, **_kwargs):
        calls.append(command)
        input_pdf = Path(command[-1])
        assert input_pdf.read_bytes() == EXAMPLE_PDF.read_bytes()
        if returncode == 0:
            dest_dir = Path(command[command.index("--dest-dir") + 1])
            (dest_dir / f"{input_pdf.stem}.html").write_text("<html>converted</html>")
            (dest_dir / "pages.css").write_text("body {}")
        process = MagicMock(returncode=returncode)

        async def communicate():
            return b"", b"" if returncode == 0 else b"conversion failed"

        process.communicate = communicate
        return process

    return fake_exec, calls


@contextmanager
def mock_http():
    """Route the task's httpx client to an in-memory transport and record its requests."""
    calls = {"get": [], "post": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            calls["get"].append(str(request.url))
            return httpx.Response(200, content=EXAMPLE_PDF.read_bytes())
        fields, files = parse_multipart(request.headers["content-type"], request.content)
        calls["post"].append(
            {
                "url": str(request.url),
                "authorization": request.headers.get("authorization"),
                "fields": fields,
                "files": files,
            }
        )
        return httpx.Response(200)

    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    with patch("shredder.tasks.httpx.AsyncClient", side_effect=client_factory):
        yield calls


async def _run_conversion(**overrides):
    kwargs = {
        "doc_path": DOC_URL,
        "call_back_url": CALLBACK_URL,
        "call_back_auth": CALLBACK_AUTH,
        "doc_provider": "url",
        "metadata": {"reference": "abc-123"},
        **overrides,
    }
    return await convert_pdf_to_html(_job_context(), **kwargs)


async def test_functional_convert_pdf_to_html():
    """The task downloads the PDF, converts it, and POSTs a zip to the callback URL."""
    fake_exec, exec_calls = _fake_pdf2htmlex()
    with (
        mock_http() as http,
        patch("shredder.tasks.asyncio.create_subprocess_exec", side_effect=fake_exec),
        patch("shredder.tasks.asyncio.to_thread", wraps=asyncio.to_thread) as to_thread,
    ):
        await _run_conversion()

    assert http["get"] == [DOC_URL]
    to_thread.assert_called_once()
    assert to_thread.call_args.args[0] is zip_directory
    assert len(exec_calls) == 1
    assert exec_calls[0][0] == str(PDF2HTMLEX)

    assert len(http["post"]) == 1
    posted = http["post"][0]
    assert posted["url"] == CALLBACK_URL
    assert posted["authorization"] == CALLBACK_AUTH
    assert posted["fields"] == {
        "job_id": "42",
        "doc_path": DOC_URL,
        "doc_provider": "url",
        "reference": "abc-123",
    }
    upload = posted["files"]["file"]
    assert upload["filename"] == "42.zip"
    assert zipfile.is_zipfile(io.BytesIO(upload["content"]))
    with zipfile.ZipFile(io.BytesIO(upload["content"])) as archive:
        names = archive.namelist()
        html_files = [n for n in names if n.endswith(".html")]
        assert len(html_files) == 1
        assert archive.read(html_files[0]) == b"<html>converted</html>"
        assert "pages.css" in names
        assert not [n for n in names if n.endswith(".zip")], "zip must not contain itself"


async def test_functional_convert_pdf_to_html_without_auth():
    """No Authorization header is sent when call_back_auth is not supplied."""
    fake_exec, _ = _fake_pdf2htmlex()
    with (
        mock_http() as http,
        patch("shredder.tasks.asyncio.create_subprocess_exec", side_effect=fake_exec),
    ):
        await _run_conversion(call_back_auth=None, metadata=None)

    posted = http["post"][0]
    assert posted["authorization"] is None
    assert set(posted["fields"]) == {"job_id", "doc_path", "doc_provider"}


async def test_functional_convert_pdf_to_html_conversion_error():
    """A failing pdf2htmlEX run raises ConversionError and nothing is POSTed."""
    fake_exec, _ = _fake_pdf2htmlex(returncode=1)
    with (
        mock_http() as http,
        patch("shredder.tasks.asyncio.create_subprocess_exec", side_effect=fake_exec),
        pytest.raises(ConversionError, match="conversion failed"),
    ):
        await _run_conversion()

    assert http["post"] == []
