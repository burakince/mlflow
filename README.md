[![Build and Publish Mlflow Docker Image Status](https://github.com/burakince/mlflow/workflows/Build%20and%20Publish%20Mlflow%20Docker%20Image/badge.svg)](https://github.com/burakince/mlflow/actions/workflows/docker-publish.yml)
![Docker Pulls](https://img.shields.io/docker/pulls/burakince/mlflow)
![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/burakince/mlflow?sort=date)
![Docker Image Version (latest semver)](https://img.shields.io/docker/v/burakince/mlflow?sort=semver)
[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/mlflow)](https://artifacthub.io/packages/search?repo=mlflow)

# Mlflow Docker Image

Please find mlflow docker images from [mlflow docker hub repository](https://hub.docker.com/r/burakince/mlflow).

# Database Requirements

The following database versions have been tested for compatibility:

- PostgreSQL: 15, 16, 17
- MySQL: 8.0, 8.4, 9.1

It is recommended to use at least the minimum tested major version of the database to ensure proper functionality and compatibility.

# Usage

Run following command

```
docker run -d -p 5000:5000 burakince/mlflow
```

## Development

Enabling Colima for testcontainers.

```bash
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export DOCKER_HOST="unix://${HOME}/.colima/docker.sock"
```
