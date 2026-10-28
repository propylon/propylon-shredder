import asyncio
import logging
import os
import tempfile
import zipfile
from pathlib import Path

import httpx

import shredder
from shredder import settings, utils

logger = logging.getLogger(__name__)


class ConversionError(Exception):
    pass


# TODO: need to inject the client from the local context
async def get_doc_from_url(doc_path: str, local_ctx: dict) -> bytes:
    """
    Downloads the document from the given URL and returns its content.
    """
    client = local_ctx["http_client"]
    response = await client.get(doc_path)
    return response.content

DOC_PROVIDER = {
    "url": get_doc_from_url,
    # TODO: Add additional providers
}


def zip_directory(src_dir: str, zip_path: str) -> None:
    """
    Zips every file under src_dir into zip_path. Blocking; run it via asyncio.to_thread.
    """
    with zipfile.ZipFile(zip_path, "w") as zip_ff:
        for root, _, files in os.walk(src_dir):
            for file in files:
                zip_ff.write(Path(root) / file, arcname=file)


async def handle_conversion(
    job_id,
    doc_path,
    call_back_url,
    call_back_auth,
    doc_provider,
    metadata
):
    """
    Handles the conversion of a PDF document to HTML using pdf2htmlEX.
    - Downloads the document from the specified provider
    - Runs the conversion
    - Stores the output in a temporary directory
    - Zips the output HTML files
    - Sends the result to the callback URL
    """

    if isinstance(settings.SHREDDER_CONVERSION_CONFIG, str):
        conversion_config = settings.SHREDDER_CONVERSION_CONFIG.split(",")
    else:
        conversion_config = [
            "--embed-css", "0",
            "--css-filename", "pages.css",
            "--process-annotation", "1",
            "--decompose-ligature", "1",
            "--bg-format", "svg",
        ]

    # Open an asynchronous http client that handles GET and Post requests for the life of the task.
    async with httpx.AsyncClient() as http_client:
        # Generate a temp file to store the downloaded PDF
        # and a temp directory for the output HTML files
        with (
            tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tff,  # The incoming PDF file
            tempfile.TemporaryDirectory(delete=True) as tdir,  # Directory for conversion output
            tempfile.TemporaryDirectory(delete=True) as zip_dir,  # Directory for the zipped output
        ):
            # Download the document from the specified provider and write it to the temp file
            doc_provider_func = DOC_PROVIDER[doc_provider]
            tff.write(
                await doc_provider_func(doc_path, local_ctx=locals())
            )
            tff.seek(0)

            # Run the PDF to HTML conversion command in a subprocess
            command = [
                "/usr/local/bin/pdf2htmlEX",  # points to the installed location in the container.
                "--dest-dir", tdir,
                *conversion_config,
                "--tmp-dir", tdir,
                tff.name,
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode:
                raise ConversionError(f"{process.returncode} {command} {stdout} {stderr}")

            # Zip the output HTML files
            # Written outside tdir so the archive does not include itself while tdir is walked.
            zip_path = f"{zip_dir}/{job_id}.zip"
            await asyncio.to_thread(zip_directory, tdir, zip_path)

            # Post the zipped result to the callback URL
            with Path(zip_path).open("rb") as zip_ff:
                headers = {}
                data = {
                    "job_id": job_id,
                    "doc_path": doc_path,
                    "doc_provider": doc_provider,
                    **(metadata or {})
                }
                if call_back_auth:
                    headers["Authorization"] = call_back_auth

                response = await http_client.post(
                    call_back_url,
                    data=data,
                    files={"file": (Path(zip_path).name, zip_ff, "application/octet-stream")},
                    headers=headers,
                )
                zip_ff_len = zip_ff.seek(0)
                logger.info(
                    "Posted result data: %s with file len %d " \
                    "to callback URL: %s, response code: %d",
                    str(data),
                    int(zip_ff_len),
                    str(call_back_url),
                    int(response.status_code)
                )


@shredder.app.task(queue=settings.PROCRASTINATE_QUEUE, pass_context=True)
async def convert_pdf_to_html(
    job_context,
    doc_path: str,
    call_back_url: str,
    call_back_auth: str | None = None,
    doc_provider: str = "url",
    metadata: dict | None = None
):
    """
    A wrapper task for the conversion function. Allows setting a job time-out.

    Inputs:
    - job_context: Automatically supplied by procrastinate when triggered.
    - doc_path: The URL pointing to the file to be converted.
    - call_back_url: The URL to post the conversion result (zip file) to.
    - call_back_auth: Optional `Bearer TOKEN` string
        for authorization header for the callback endpoint.
    - doc_provider: The provider to fetch the document from. Only "url" is currently supported.
    - metadata: Optional passed-through metadata dict/JSON to include in the callback.
    """
    job_id = job_context.job.id

    @utils.set_timeout(settings.PROCRASTINATE_MAX_JOB_TTL)
    async def _run_job(*args):
        return await handle_conversion(*args)

    return await _run_job(job_id, doc_path, call_back_url, call_back_auth, doc_provider, metadata)
