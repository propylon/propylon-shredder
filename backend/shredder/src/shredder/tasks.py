import asyncio
import logging
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

import requests

import shredder
from shredder import settings, utils

logger = logging.getLogger(__name__)

# async def get_doc_from_url(doc_path: str) -> str:
#     """
#     Downloads the document from the given URL and returns the local file path.
#     """
#     return requests.get(doc_path).content


# async def get_doc_from_s3(doc_path: str) -> str:
#     """
#     Downloads the document from the given URL and returns the local file path.
#     """
#     import boto3
#     boto3.client
#     return ...


# DOC_PROVIDER = {
#     "url": get_doc_from_url,
#     "s3": get_doc_from_s3,
# }

async def handle_conversion(job_id, doc_path, call_back_url, doc_provider, metadata):
    """
    Handles the conversion of a PDF document to HTML using pdf2htmlEX.
    - Downloads the document from the specified provider
    - Runs the conversion
    - Stores the output in a temporary directory
    - Zips the output HTML files
    - Sends the result to the callback URL
    """

    # Generate a temp file to store the downloaded PDF
    # and a temp directory for the output HTML files
    with (
        tempfile.NamedTemporaryFile(suffix=".pdf") as tff,
        tempfile.TemporaryDirectory() as tdir
    ):
        # Download the document from the specified provider and write it to the temp file
        # tff.write(await DOC_PROVIDER[doc_provider](doc_path))
        tff.write(requests.get(doc_path).content)

        # Run the PDF to HTML conversion command in a subprocess
        command = [
            "/usr/local/bin/pdf2htmlEX",  # points to the installed location in the container.
            "--embed", "cfijo",
            "--split-pages", "1",
            "--dest-dir", tdir,
            "--page-filename", f"{job_id}-%d.page",
            tff.name,
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode:
            raise Exception(f"{process.returncode} {command} {stdout} {stderr}")
            # raise subprocess.CalledProcessError(
            #     process.returncode, command, output=stdout, stderr=stderr
            # )

        # Zip the output HTML files
        with zipfile.ZipFile(f"{tdir}/{job_id}.zip", "w") as zip_ff:
            for root, _, files in os.walk(tdir):
                for file in files:
                    this_file_path = Path(root) / file
                    with this_file_path.open("rb") as this_ff:
                        zip_ff.write(
                            this_ff,
                            arcname=file
                        )

        # Post the zipped result to the callback URL
        data = {
            "file": zip_ff,
            "job_id": job_id,
            "doc_path": doc_path,
            "doc_provider": doc_provider,
            **(metadata or {})
        }
        with Path(f"{tdir}/{job_id}.zip").open("rb") as zip_ff:
            response = requests.post(
                call_back_url,
                data=data
            )
        logger.info(
            "Posted result data: %s to callback URL: %s, response: %s",
            str(data),
            call_back_url,
            response.status_code
        )


@shredder.app.task(queue=settings.PROCRASTINATE_QUEUE, pass_context=True)
async def convert_pdf_to_html(
    job_context, doc_path: str, call_back_url: str, doc_provider: str = "url", metadata: dict | None = None
):
    """
    - ...
    NOTE: only one doc_provider currently supported: GET from "url"
    """
    job_id = job_context.job.id

    @utils.set_timeout(settings.MAX_JOB_TTL)
    async def _run_job(*args):
        return await handle_conversion(*args)

    return await _run_job(job_id, doc_path, call_back_url, doc_provider, metadata)
