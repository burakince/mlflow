import base64
import json
import os
import time

import psycopg2
import pytest
import requests
from werkzeug.security import generate_password_hash

from ..helpers.extended_docker_compose import ExtendedDockerCompose


@pytest.mark.parametrize("distro", ["debian", "alpine"])
def test_postgres_backended_model_upload_and_access_with_oidc_auth(
    distro, test_model, training_params, conda_env
):
    """Test OIDC authentication with MLflow using Keycloak as the identity provider."""
    os.environ["DISTRO"] = distro

    with ExtendedDockerCompose(
        context=".",
        compose_file_name=["docker-compose.oidc-auth-postgres-test.yaml"],
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

        compose.wait_for_logs("keycloak", ".*Listening on.*8090.*", timeout=300)
        compose.wait_for_logs("mlflow", ".*Uvicorn running.*", timeout=600)
        compose.wait_for_logs("mlflow", ".*Application startup complete.*", timeout=300)
        compose.wait_for_logs("mlflow", ".*8606fa83a998.*initial_migration.*", timeout=120)
        time.sleep(5)  # Wait for services to stabilize

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

        # Decode JWT to get user info (mlflow-oidc-auth requires user in DB for Bearer tokens)
        token_parts = access_token.split(".")
        payload = token_parts[1] + "=" * (4 - len(token_parts[1]) % 4)
        token_data = json.loads(base64.urlsafe_b64decode(payload))
        user_email = (token_data.get("email") or token_data.get("preferred_username")).lower()
        user_name = token_data.get("name") or user_email
        user_groups = token_data.get("groups", [])
        is_admin = any("mlflow-admin" in g for g in user_groups)

        # Create user in OIDC database (required for Bearer token auth)
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
                cur.execute("SELECT 1 FROM users WHERE username = %s", (user_email,))
                if not cur.fetchone():
                    cur.execute(
                        """INSERT INTO users (username, display_name, password_hash, is_admin)
                           VALUES (%s, %s, %s, %s)""",
                        (user_email, user_name, generate_password_hash("x"), is_admin),
                    )
                    conn.commit()

        experiment_name = "oidc-auth-postgres-experiment"
        model_name = "test-oidc-auth-pg-model"

        os.environ["MLFLOW_S3_ENDPOINT_URL"] = f"http://{minio_host}:{minio_port}"
        os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"

        headers = {"Authorization": f"Bearer {access_token}"}

        create_exp_response = requests.post(
            f"{base_url}/api/2.0/mlflow/experiments/create",
            json={"name": experiment_name},
            headers=headers,
            timeout=30,
        )
        assert create_exp_response.status_code in [
            200,
            409,
        ], f"Failed to create experiment: {create_exp_response.status_code}: {create_exp_response.text}"

        get_exp_response = requests.get(
            f"{base_url}/api/2.0/mlflow/experiments/get-by-name",
            params={"experiment_name": experiment_name},
            headers=headers,
            timeout=30,
        )
        assert (
            get_exp_response.status_code == 200
        ), f"Failed to get experiment: {get_exp_response.status_code}: {get_exp_response.text}"
        experiment_id = get_exp_response.json()["experiment"]["experiment_id"]

        create_run_response = requests.post(
            f"{base_url}/api/2.0/mlflow/runs/create",
            json={"experiment_id": experiment_id, "start_time": int(time.time() * 1000)},
            headers=headers,
            timeout=30,
        )
        assert (
            create_run_response.status_code == 200
        ), f"Failed to create run: {create_run_response.status_code}: {create_run_response.text}"

        create_model_response = requests.post(
            f"{base_url}/api/2.0/mlflow/registered-models/create",
            json={"name": model_name},
            headers=headers,
            timeout=30,
        )
        assert create_model_response.status_code in [
            200,
            409,
        ], f"Failed to register model: {create_model_response.status_code}: {create_model_response.text}"

        get_model_response = requests.get(
            f"{base_url}/api/2.0/mlflow/registered-models/get",
            params={"name": model_name},
            headers=headers,
            timeout=30,
        )
        assert (
            get_model_response.status_code == 200
        ), f"Failed to get model: {get_model_response.status_code}: {get_model_response.text}"
        assert (
            get_model_response.json()["registered_model"]["name"] == model_name
        ), f"Model name mismatch: expected {model_name}"

        compose.stop()
