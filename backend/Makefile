# Import all constants from .env file.
# defaults set in the .env file will be applied to the commands below.
include .env
export

# Allow passing extra args, e.g. make docker -- --build
%:
	@:

UV=~/.local/bin/uv
IN_ENV=$(UV) run

# ====================
# Build
# ====================

# Running make env does not overwrite the existing venv folder
env:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	$(UV) venv --allow-existing --python $(PYTHON_VERSION) $(ENV_DIR)
	@printf "Environment installed at $(ENV_DIR), run the following command to activate it: \n$(IN_ENV)\n"

# Build the environment
build:
	$(UV) sync --locked --group dev

env-update:
	$(UV) lock --upgrade

# ====================
# Clean
# ====================

clean:
	- @rm -rf ./*.egg-info
	- @find ./ -name '*.pyc' -delete
	- @find ./ -name '__pycache__' | xargs rm -rf
	- @rm -f ./.pytest_coverage.*

clean-env: clean
	- @rm -rf $(ENV_DIR)

clean-all: clean clean-env
	@echo "Removed the virtual environment, build-files, and cached-files."

# ====================
# Docker
# ====================

docker-network:
	-docker network create $(DOCKER_NETWORK_NAME)

docker: docker-network
	$(IN_ENV) docker-compose -p $(DOCKER_COMPOSE_PROJECT) up -d $(filter-out $@,$(MAKECMDGOALS))

# ====================
# Formatting / Linting
# ====================

# Runs ruff check and fix using the pyproject.toml config
# TEMP: using unsafe fixes to speed things up
fixup:
	$(IN_ENV) $(UV) run ruff check --fix

lint:
	$(IN_ENV) $(UV) run ruff check
	$(IN_ENV) $(UV) run ty check

# ====================
# Testing
# ====================

test:
	$(IN_ENV) py.test $(filter-out $@,$(MAKECMDGOALS))

test-cov:
	COVERAGE_PROCESS_START=pyproject.toml COVERAGE_FILE=.pytest_coverage $(IN_ENV) coverage run -m pytest
	- COVERAGE_FILE=.pytest_coverage $(IN_ENV) coverage combine
	COVERAGE_FILE=.pytest_coverage $(IN_ENV) coverage report

test-cov-html:
	COVERAGE_PROCESS_START=pyproject.toml COVERAGE_FILE=.pytest_coverage $(IN_ENV) coverage run -m pytest
	- COVERAGE_FILE=.pytest_coverage $(IN_ENV) coverage combine
	COVERAGE_FILE=.pytest_coverage $(IN_ENV) coverage html
