#!/usr/bin/env ash

set -e

set -a
. /propylon/.env
set +a

export PYTHONPATH=/propylon/shredder/src

echo "Starting worker..."

# Run 1 ingest workers running a max of WORKER_CONCURRENCY at a time with WORKER_QUEUES queues
WORKER_QUEUES="${PROCRASTINATE_QUEUE:?PROCRASTINATE_QUEUE is not set}"
WORKER_CONCURRENCY="${PROCRASTINATE_CONCURRENCY:?PROCRASTINATE_CONCURRENCY is not set}"
exec procrastinate --log-format "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s" worker -q "$WORKER_QUEUES" -c "$WORKER_CONCURRENCY"

# NOTE: exec lets the worker receive Docker’s shutdown signals directly
