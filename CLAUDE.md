# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A custom MLflow Docker image distribution (`burakince/mlflow`) that packages MLflow with multi-cloud support (AWS S3/MinIO, GCP Cloud Storage, Azure Blob Storage) and optional LDAP authentication. The `mlflowstack` Python package is built via Poetry, installed into a venv inside the Docker image, and published to Docker Hub as both `debian` and `alpine` variants.

## Commands

### Setup

```bash
# Install dependencies (creates .venv in-project per poetry.toml)
poetry install --no-interaction
```

### Testing

```bash
# Run all tests
poetry run pytest

# Run only unit tests (no Docker required)
poetry run pytest tests/unit/

# Run a single test file
poetry run pytest tests/unit/test_lldap.py

# Run a single test by name
poetry run pytest tests/unit/test_lldap.py::test_resolve_user_lldap_admin_from_dn

# Run integration tests (requires Docker)
# Integration tests need .env vars AND Colima socket vars (see "Local dev with Colima"):
source .env && poetry run pytest tests/integration/
```

### Docker

```bash
# Build debian image locally
docker build -f Dockerfile-debian -t burakince/mlflow:local .

# Build alpine image locally
docker build -f Dockerfile-alpine -t burakince/mlflow:local-alpine .

# Run the image
docker run -d -p 5000:5000 burakince/mlflow:local
```

### Local dev with Colima (testcontainers)

```bash
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export DOCKER_HOST="unix://${HOME}/.colima/docker.sock"
```

## Integration Test Constraints

### Port mappings must be dynamic
All `docker-compose.*-test.yaml` files use `"0:PORT"` (never `"PORT:PORT"`). Tests are parametrized over `["debian", "alpine"]` and run sequentially with the same container names — fixed ports cause `address already in use` failures. `compose.get_service_host/port()` queries the actual assigned port at runtime so no test code changes are needed.

Services accessed **only within the compose network** (postgres, mysql, mssql, lldap, usersdb) have **no** `ports:` section at all — only services the test code connects to directly (mlflow, minio, azurite, fake-gcs) use `"0:PORT"`.

### MLflow healthcheck is required in all compose files
All compose files include a Python-based healthcheck on `/health`:
```yaml
healthcheck:
  test: ["CMD", "/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
  interval: 10s
  timeout: 10s
  retries: 15
  start_period: 60s
```
Without it, `docker compose up --wait` returns before MLflow finishes DB migrations. With `restart: always` + dynamic ports, a container restart assigns a **new** random host port — the test then connects to the dead old one.

### `wait_for_logs` uses container port, not host port
Uvicorn logs `Uvicorn running on http://0.0.0.0:8080` using the **container-internal** port (8080), not the dynamic host-mapped port. The pattern in basic-auth tests uses a broad match that covers both uvicorn and gunicorn startup messages:
```python
log_message = r".*http://0\.0\.0\.0:8080.*"  # container port, always 8080
```
Do not use `f".*{re.escape(base_url)}.*"` — that embeds the dynamic host port which will never match the container log.

### Alembic migration log (`8606fa83a998`) does not appear in MLflow 3.x
The `alembic.runtime.migration` logger is not configured in MLflow 3.x, so revision IDs never appear in container output. Waiting for the startup URL log is sufficient — migrations complete before uvicorn binds.

### Uvicorn is the server
Basic-auth compose files use `--uvicorn-opts='--log-level debug'`. Non-auth compose files run uvicorn in single-worker mode (no `--workers` flag).

### MySQL requires `--log-bin-trust-function-creators=1`
MLflow 3.12+ creates triggers (e.g. `prevent_secrets_aad_mutation` on the `secrets` table) during migration. MySQL 8+/9+ blocks trigger creation for non-SUPER users when binary logging is enabled. All primary MySQL services (not `usersdb`) must include this flag:
```yaml
command: --innodb-buffer-pool-size=256m --log-bin-trust-function-creators=1
```
Without it, `docker compose up --wait` fails because the mlflow container exits with `OperationalError: (1419, 'You do not have the SUPER privilege and binary logging is enabled')`.

### MySQL and MSSQL memory limits (GitHub Actions)
All MySQL and MSSQL services include startup options to stay within the 7 GB GitHub Actions runner limit:
- MySQL primary: `command: --innodb-buffer-pool-size=256m --log-bin-trust-function-creators=1`
- MySQL `usersdb`: `command: --innodb-buffer-pool-size=128m`
- MSSQL: `MSSQL_MEMORY_LIMIT_MB: "1500"` (SQL Server's native env var)

## Architecture

### Package: `mlflowstack/`

The sole source module. Currently contains one subpackage:

- **`mlflowstack/auth/ldap.py`** — A custom MLflow auth function (`authenticate_request_basic_auth`) that replaces MLflow's built-in basic auth. It authenticates against an LDAP/LDAPS server using `ldap3`, resolves the user's group membership to determine admin vs. regular user role, then creates/updates the user in MLflow's own auth store. Configured entirely via environment variables (`LDAP_URI`, `LDAP_LOOKUP_BIND`, `LDAP_GROUP_*`, etc.). Wired into MLflow via `basic_auth.ini`'s `authorization_function` key.

### Tests: `tests/`

- **`tests/unit/`** — Pure unit tests using `pytest-mock`. Currently covers `mlflowstack.auth.ldap` (group membership resolution, dn vs. attribute matching). No Docker required.
- **`tests/integration/`** — Full end-to-end integration tests using `testcontainers` (`DockerCompose`). Each test spins up the actual built Docker image alongside real databases and object stores using the `docker-compose.*.yaml` files.
- **`tests/helpers/`** — Shared utilities: `ExtendedDockerCompose` (adds `wait_for_logs` / `get_service_logs` on top of `DockerCompose`; `get_service_logs` uses compose-scoped `get_logs()` — not the Docker SDK — to avoid matching containers from other test runs) and `certificates.py` (generates self-signed CA + server certs for SSL LDAP tests).

### Integration test matrix

Each `docker-compose.*-test.yaml` file maps to one integration test file. The naming convention is `<cloud>-<database>`:

| Cloud / Auth | Databases |
|---|---|
| AWS (MinIO for S3) | postgres, mysql, mssql |
| Azure (Azurite) | postgres, mysql, mssql |
| GCP (fake-gcs-server) | postgres, mysql, mssql |
| Basic auth | postgres, mysql |
| LDAP auth | postgres (lldap container) |
| LDAP + SSL auth | postgres (lldap + generated certs) |

### Docker image build

Both Dockerfiles use a two-stage build:
1. **`foundation`** stage — installs Poetry, builds the `mlflowstack` wheel via `poetry build`, creates `/opt/venv`, and installs the wheel into it.
2. **Final slim stage** — copies only `/opt/venv` from foundation, creates a non-root `mlflow` user (UID/GID 1001), exposes port 5000.

When updating the Python base image patch version in the Dockerfiles, also update the Image Variants table in `README.md` to match. The CI runner in `docker-publish.yml` uses a floating `python-version: '3.13'` — this is intentional, do not pin it to a patch version.

The `DISTRO` env var (set in integration tests via `os.environ["DISTRO"]`) controls which Dockerfile (`Dockerfile-debian` or `Dockerfile-alpine`) Docker Compose uses for the `mlflow` service in each test.

### CI/CD (`.github/workflows/docker-publish.yml`)

Pipeline order: `integrationtest` → `buildtestpush` → `deprecationandcleaning`. Integration tests run against three Postgres/MySQL version combos from `.env`. After tests pass, both variants are built for `linux/amd64` and `linux/arm64/v8`, scanned with Snyk, and pushed to Docker Hub + GHCR on semver tags only. Images are signed with Cosign.

### Key configuration files

- **`.env`** — Canonical versions for all external services (Postgres, MySQL, MinIO, MSSQL, lldap, fake-gcs-server, Azurite). Used both locally and in CI.
- **`test-containers/basic-auth/*/basic_auth.ini`** — MLflow auth config files mounted into the container during integration tests. The LDAP variant points `authorization_function` at `mlflowstack.auth.ldap:authenticate_request_basic_auth`.
- **`poetry.toml`** — Forces Poetry to create the venv in-project (`.venv/`).

### `amd64_only` test marker

Integration tests marked `@pytest.mark.amd64_only` are skipped automatically on non-x86_64 hosts (enforced in `tests/integration/conftest.py`). MSSQL tests use this marker since the SQL Server image only supports amd64.
