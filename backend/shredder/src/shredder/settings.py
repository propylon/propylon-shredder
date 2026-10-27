import os

MAX_JOB_TTL = 600  # seconds. maximum time a job is allowed to run before being force-failed

PROCRASTINATE_QUEUE = os.getenv("PROCRASTINATE_QUEUE", "shredder_queue")
PROCRASTINATE_WORKER = os.getenv("PROCRASTINATE_WORKER", "shredder_worker")
PROCRASTINATE_TASK_PATHS = os.environ["PROCRASTINATE_TASK_PATHS"].split(",")


PROCRASTINATE_DB_USER = os.environ["PROCRASTINATE_DB_USER"],
PROCRASTINATE_DB_PASSWORD = os.environ["PROCRASTINATE_DB_PASSWORD"],
PROCRASTINATE_DB_HOST = os.environ["PROCRASTINATE_DB_HOST"],
PROCRASTINATE_DB_PORT = os.environ["PROCRASTINATE_DB_PORT"],
PROCRASTINATE_DB_NAME = os.environ["PROCRASTINATE_DB_NAME"],

# S3_CONFIG = {
#     "STORAGE_ACCESS_ID": os.getenv("STORAGE_ACCESS_ID"),
#     "STORAGE_SECRET_KEY": os.getenv("STORAGE_SECRET_KEY"),
#     "STORAGE_BUCKET_NAME": os.getenv("STORAGE_BUCKET_NAME", "my-bucket"),
#     "STORAGE_ENDPOINT_URL": os.getenv("S3_ENDPOINT_URL", "localhost"),
#     "STORAGE_ADDRESSING_STYLE": os.getenv("S3_ADDRESSING_STYLE", "path"),
#     "STORAGE_DEFAULT_ACL": os.getenv("DEFAULT_ACL"),
# }
