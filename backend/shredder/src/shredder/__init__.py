import procrastinate
from procrastinate.manager import JobManager

from shredder import exceptions, settings, utils

if all((
    settings.MONITORING_ENABLED,
    settings.SENTRY_ENVIRONMENT,
    settings.SENTRY_ENDPOINT,
)):
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_ENDPOINT,
        environment=settings.SENTRY_ENVIRONMENT,
        integrations=[
            LoggingIntegration(),
        ],
    )
elif (
    settings.MONITORING_ENABLED and
    not all((settings.SENTRY_ENVIRONMENT, settings.SENTRY_ENDPOINT))
):
    raise exceptions.ShredderError(
        "Sentry is enabled but SENTRY_ENVIRONMENT or SENTRY_ENDPOINT is not set."
    )

DB_CONFIG_FSTRING = "postgres://{user}:{password}@{host}:{port}/{dbname}"

PG_CONNECTOR = procrastinate.PsycopgConnector(
    conninfo=DB_CONFIG_FSTRING.format(
        user=settings.PROCRASTINATE_DB_USER,
        password=settings.PROCRASTINATE_DB_PASSWORD,
        host=settings.PROCRASTINATE_DB_HOST,
        port=settings.PROCRASTINATE_DB_PORT,
        dbname=settings.PROCRASTINATE_DB_NAME,
    )
)

JOB_MANAGER = JobManager(connector=PG_CONNECTOR)

task_path_list = settings.PROCRASTINATE_TASK_PATHS

app = procrastinate.App(import_paths=task_path_list, connector=PG_CONNECTOR)

__all__ = [
    "settings",
    "utils",
]
