import os

import procrastinate
from procrastinate.manager import JobManager

from shredder import settings, utils

WORKERS = {
    settings.PROCRASTINATE_WORKER: {"queues": settings.PROCRASTINATE_QUEUES.split(",")},
}

DB_CONFIG_FSTRING = "postgres://{user}:{password}@{host}:{port}/{dbname}"

PG_CONNECTOR = procrastinate.PsycopgConnector(
    conninfo=DB_CONFIG_FSTRING.format(
        user=os.environ["PROCRASTINATE_DB_USER"],
        password=os.environ["PROCRASTINATE_DB_PASSWORD"],
        host=os.getenv("PROCRASTINATE_DB_HOST", "127.0.0.1"),
        port=os.environ["PROCRASTINATE_DB_PORT"],
        dbname=os.environ["PROCRASTINATE_DB_NAME"],
    )
)

JOB_MANAGER = JobManager(connector=PG_CONNECTOR)

task_path_list = settings.PROCRASTINATE_TASK_PATHS

app = procrastinate.App(import_paths=task_path_list, connector=PG_CONNECTOR)

__all__ = [
    "settings",
    "utils",
]
