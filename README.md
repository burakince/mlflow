[![Build and Publish Mlflow Docker Image Status](https://github.com/burakince/mlflow/workflows/Build%20and%20Publish%20Mlflow%20Docker%20Image/badge.svg)](https://github.com/burakince/mlflow/actions/workflows/docker-publish.yml)
![Docker Pulls](https://img.shields.io/docker/pulls/burakince/mlflow)
![Docker Image Size (tag)](https://img.shields.io/docker/image-size/burakince/mlflow/latest)
[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/mlflow)](https://artifacthub.io/packages/search?repo=mlflow)

# Mlflow Docker Image

A production-ready MLflow Docker image with multi-cloud artifact storage and optional LDAP authentication, published to [Docker Hub](https://hub.docker.com/r/burakince/mlflow).

## Image Variants

| Tag suffix | Base |
|---|---|
| *(none)* / `latest` | `python:3.13.13-slim` (Debian) |
| `-alpine` | `python:3.13.13-alpine` |

Both variants run as a non-root `mlflow` user (UID/GID 1001) and install all dependencies into `/opt/venv`.

## Storage Backends

| Cloud | Artifact store |
|---|---|
| AWS / MinIO | S3 (`s3://`) via `boto3` |
| Google Cloud | GCS (`gs://`) via `google-cloud-storage` |
| Azure | Blob Storage (`wasbs://`) via `azure-storage-blob` |

Set `--default-artifact-root` to the appropriate URI when starting the server.

## Authentication

### Basic auth

Pass `--app-name basic-auth` to enable MLflow's built-in basic authentication.

### OIDC authentication

Pass `--app-name oidc-auth` to enable [mlflow-oidc-auth](https://github.com/data-platform-hq/mlflow-oidc-auth) and configure via environment variables:

| Variable | Description |
|---|---|
| `OIDC_DISCOVERY_URL` | OpenID Connect discovery endpoint, e.g. `https://keycloak/realms/myrealm/.well-known/openid-configuration` |
| `OIDC_CLIENT_ID` | OAuth2 client ID |
| `OIDC_CLIENT_SECRET` | OAuth2 client secret |
| `OIDC_REDIRECT_URI` | Callback URI, e.g. `http://mlflow:8080/oidc/callback` |
| `OIDC_SCOPE` | Requested scopes, e.g. `openid,email,profile,groups` |
| `OIDC_USERS_DB_URI` | SQLAlchemy URI for the OIDC users database |
| `OIDC_GROUP_NAME` | Group that grants regular-user access |
| `OIDC_ADMIN_GROUP_NAME` | Group that grants admin access |
| `DEFAULT_MLFLOW_PERMISSION` | Default permission for authenticated users, e.g. `MANAGE` |

### LDAP/LDAPS authentication

Point `authorization_function` in `basic_auth.ini` at `mlflowstack.auth.ldap:authenticate_request_basic_auth` and configure via environment variables:

| Variable | Description |
|---|---|
| `LDAP_URI` | LDAP server URI, e.g. `ldap://host:3890/dc=example,dc=com` |
| `LDAP_LOOKUP_BIND` | Bind DN template, e.g. `uid=%s,ou=people,dc=example,dc=com` |
| `LDAP_GROUP_ATTRIBUTE` | `dn` or an attribute name |
| `LDAP_GROUP_SEARCH_BASE_DN` | Base DN for group search |
| `LDAP_GROUP_SEARCH_FILTER` | LDAP filter for group membership |
| `LDAP_GROUP_USER_DN` | DN of the regular-user group |
| `LDAP_GROUP_ADMIN_DN` | DN of the admin group |
| `LDAP_CA` | Path to CA certificate (LDAPS only) |
| `LDAP_TLS_VERIFY` | TLS verification mode (LDAPS only) |

## Database Requirements

The following databases have been tested for compatibility:

- PostgreSQL
- MySQL
- Microsoft SQL Server

See [`.env`](./.env) for the tested versions. Use at least the minimum tested major version.

### MySQL note

MLflow 3.12+ creates triggers during migration. MySQL 8+/9+ requires `log_bin_trust_function_creators=ON` when binary logging is enabled (the default) and the MLflow user is not `root`. Start MySQL with:

```
--log-bin-trust-function-creators=1
```

## Usage

```bash
docker run -d -p 5000:5000 burakince/mlflow
```

The server exposes a `/health` endpoint that returns `200 OK` once fully initialised (migrations complete, ready to accept requests).

## Prometheus Metrics

The image includes [prometheus-flask-exporter](https://github.com/rycus86/prometheus_flask_exporter). MLflow exposes a `/metrics` endpoint when the exporter is enabled via the standard Flask/Prometheus integration.

## Security Context

The Docker image runs as a non-root user (`mlflow`) with the following default settings:

- **User ID (UID)**: 1001
- **Group ID (GID)**: 1001

The Python virtual environment is located at `/opt/venv` in both the Debian and Alpine images.

## Development

Enabling Colima for testcontainers:

```bash
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export DOCKER_HOST="unix://${HOME}/.colima/docker.sock"
```

## Contributions

![Alt](https://repobeats.axiom.co/api/embed/79f658ee4736137b7fbcc5cab6abcf1b078c39ab.svg "Repobeats analytics image")
