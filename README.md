[![Build and Publish Mlflow Docker Image Status](https://github.com/burakince/mlflow/workflows/Build%20and%20Publish%20Mlflow%20Docker%20Image/badge.svg)](https://github.com/burakince/mlflow/actions/workflows/docker-publish.yml)
![Docker Pulls](https://img.shields.io/docker/pulls/burakince/mlflow)
![Docker Image Size (tag)](https://img.shields.io/docker/image-size/burakince/mlflow/latest)
[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/mlflow)](https://artifacthub.io/packages/search?repo=mlflow)

# Mlflow Docker Image

Please find mlflow docker images from [mlflow docker hub repository](https://hub.docker.com/r/burakince/mlflow).

# Database Requirements

The following databases have been tested for compatibility:

- PostgreSQL
- MySQL
- Microsoft SQL Server

Please find tested database versions from [this](./.env) file.

It is recommended to use at least the minimum tested major version of the database to ensure proper functionality and compatibility.

# Usage

Run following command

```
docker run -d -p 5000:5000 burakince/mlflow
```

## Security Context

The Docker image runs as a non-root user (`mlflow`) with the following default settings:

- **User ID (UID)**: 1001
- **Group ID (GID)**: 1001

The python virtual environment located under `/opt` folder for both debian and alpine based images. You can more details from `/opt/venv/` directory.

## Development

Enabling Colima for testcontainers.

```bash
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export DOCKER_HOST="unix://${HOME}/.colima/docker.sock"
```

## Contributions

![Alt](https://repobeats.axiom.co/api/embed/79f658ee4736137b7fbcc5cab6abcf1b078c39ab.svg "Repobeats analytics image")
