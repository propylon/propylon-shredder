#!/usr/bin/env bash

# Re-exec under bash if something invoked this script with a different shell (e.g. a container/task command override using sh).
if [ -z "$BASH_VERSION" ]; then
  exec bash "$0" "$@"
fi

set -e

# When running locally, .env gets exported into the environment through make file and/or docker-compose.
# When deploying to cloud, source the generated .env file
if [ "$ENV_TYPE" = "remote" ] && [ -f /apps/.env ]; then
  set -o allexport
  . /apps/.env
  set +o allexport
fi

export PYTHONPATH=/apps

pids=()
# Forward SIGTERM/SIGINT to all worker processes so Procrastinate can shut down gracefully when container is stopped/rebooted
term_handler() {
  for pid in "${pids[@]}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait
  exit 0
}
trap term_handler SIGTERM SIGINT

echo "Starting worker..."

# Run 1 ingest workers running a max of WORKER_CONCURRENCY at a time with WORKER_QUEUES queues
WORKER_QUEUES="${PROCRASTINATE_QUEUES:?PROCRASTINATE_QUEUES is not set}"
WORKER_CONCURRENCY="${PROCRASTINATE_CONCURRENCY:?PROCRASTINATE_CONCURRENCY is not set}"
procrastinate --log-format "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s" worker -q "$WORKER_QUEUES" -c "$WORKER_CONCURRENCY" &  
pids+=($!)

# Wait for all background jobs; if any exits, script exits too  
wait -n  
exit $?
