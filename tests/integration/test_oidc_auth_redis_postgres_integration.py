import os
import secrets
import time

import psycopg2
import pytest
import redis
import requests

import mlflow
from mlflow import MlflowClient

from ..helpers.extended_docker_compose import ExtendedDockerCompose


@pytest.mark.parametrize("distro", ["debian", "alpine"])
def test_postgres_redis_backended_model_upload_and_access_with_oidc_auth(
    distro, test_model, training_params, conda_env
):
    os.environ["DISTRO"] = distro

    with ExtendedDockerCompose(
        context=".",
        compose_file_name=["docker-compose.oidc-auth-redis-postgres-test.yaml"],
        build=True,
    ) as compose:
        mlflow_host = compose.get_service_host("mlflow", 8080)
        mlflow_port = compose.get_service_port("mlflow", 8080)
        minio_host = compose.get_service_host("minio", 9000)
        minio_port = compose.get_service_port("minio", 9000)
        keycloak_host = compose.get_service_host("keycloak", 8090)
        keycloak_port = compose.get_service_port("keycloak", 8090)

        base_url = f"http://{mlflow_host}:{mlflow_port}"
        keycloak_url = f"http://{keycloak_host}:{keycloak_port}"

        log_message = r".*http://0\.0\.0\.0:8080.*"
        compose.wait_for_logs("mlflow", log_message)
        time.sleep(5)  # Wait 5 seconds more to get flask ready

        # Get OIDC token from Keycloak
        token_response = requests.post(
            f"{keycloak_url}/realms/mlflow-test/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "mlflow-client",
                "client_secret": "mlflow-client-secret",
                "username": "testuser",
                "password": "testpassword",
                "scope": "openid email profile",
            },
            timeout=30,
        )
        assert token_response.status_code == 200, f"Failed to get token: {token_response.text}"
        access_token = token_response.json()["access_token"]

        # Trigger lazy store initialization so Alembic migrations run in oidc_users DB.
        # The 404 response is expected — token is valid but user not yet provisioned.
        requests.get(
            f"{base_url}/api/2.0/mlflow/users",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        # Pre-create user in OIDC database.
        # mlflow-oidc-auth 7.x requires users to pre-exist for Bearer token auth.
        oidc_db_host = compose.get_service_host("oidc-users-db", 5432)
        oidc_db_port = compose.get_service_port("oidc-users-db", 5432)
        with psycopg2.connect(
            host=oidc_db_host,
            port=oidc_db_port,
            database="oidc_users",
            user="postgres",
            password="postgres",
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (username) DO NOTHING""",
                    ("testuser@mlflow.test", "Test User", secrets.token_hex(32), False, False),
                )
                conn.commit()

        experiment_name = "oidc-auth-redis-postgres-experiment"
        model_name = "test-oidc-auth-redis-pg-model"
        stage_name = "Staging"

        os.environ["MLFLOW_TRACKING_TOKEN"] = access_token
        os.environ["MLFLOW_S3_ENDPOINT_URL"] = f"http://{minio_host}:{minio_port}"
        os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"

        mlflow.set_tracking_uri(base_url)
        mlflow.set_experiment(experiment_name)
        experiment = mlflow.get_experiment_by_name(experiment_name)

        with mlflow.start_run(experiment_id=experiment.experiment_id) as run:
            mlflow.log_params(training_params)
            mlflow.pyfunc.log_model("model", conda_env=conda_env, python_model=test_model)
            model_uri = f"runs:/{run.info.run_id}/model"
            model_details = mlflow.register_model(model_uri, model_name)

            mlflow_client = MlflowClient()
            mlflow_client.set_registered_model_alias(
                name=model_details.name,
                alias=stage_name,
                version=model_details.version,
            )

        params = {"name": model_name, "alias": stage_name}
        latest_version_url = f"{base_url}/api/2.0/mlflow/registered-models/alias"
        r = requests.get(
            url=latest_version_url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=300,
        )

        assert model_name == r.json()["model_version"]["name"]
        assert "1" == r.json()["model_version"]["version"]
        assert "READY" == r.json()["model_version"]["status"]
        assert "Staging" == r.json()["model_version"]["aliases"][0]

        # Verify Redis cache is being used by confirming keys were written
        redis_host = compose.get_service_host("redis", 6379)
        redis_port = compose.get_service_port("redis", 6379)
        redis_client = redis.Redis(host=redis_host, port=int(redis_port), decode_responses=True)
        cache_keys = redis_client.keys("mlflow_oidc_auth:*")
        assert len(cache_keys) > 0, "Expected Redis cache keys from mlflow-oidc-auth but found none"

        compose.stop()
