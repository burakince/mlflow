import os
import re
import time

import requests

import mlflow
from mlflow.server.auth.client import AuthServiceClient
from mlflow.tracking.client import MlflowClient

from .extended_docker_compose import ExtendedDockerCompose


def test_postgres_backended_model_upload_and_access_with_basic_auth(
    test_model, training_params, conda_env
):
    with ExtendedDockerCompose(
        context=".",
        compose_file_name=["docker-compose.basic-auth-postgres-test.yaml"],
        # pull=True,
        build=True,
    ) as compose:
        mlflow_host = compose.get_service_host("mlflow", 8080)
        mlflow_port = compose.get_service_port("mlflow", 8080)
        minio_host = compose.get_service_host("minio", 9000)
        minio_port = compose.get_service_port("minio", 9000)

        mlflow_admin_username = "testuser"
        mlflow_admin_password = "simpletestpassword"

        mlflow_user_username = "basicuser"
        mlflow_user_password = "userpassword1"

        base_url = f"http://{mlflow_host}:{mlflow_port}"

        log_message = f".*Listening at: {re.escape(base_url)}.*"
        compose.wait_for_logs("mlflow", log_message)
        compose.wait_for_logs("mlflow", ".*8606fa83a998, initial_migration")
        time.sleep(5)  # Wait 5 seconds more the get flask ready

        experiment_name = "basic-auth-postgres-experiment"
        model_name = "test-basic-auth-pg-model"
        stage_name = "Staging"
        os.environ["MLFLOW_TRACKING_USERNAME"] = mlflow_admin_username
        os.environ["MLFLOW_TRACKING_PASSWORD"] = mlflow_admin_password

        mlflow_auth_client = AuthServiceClient(base_url)
        mlflow_auth_client.create_user(mlflow_user_username, mlflow_user_password)

        os.environ["MLFLOW_TRACKING_USERNAME"] = mlflow_user_username
        os.environ["MLFLOW_TRACKING_PASSWORD"] = mlflow_user_password

        mlflow.set_tracking_uri(base_url)
        mlflow.set_experiment(experiment_name)
        experiment = mlflow.get_experiment_by_name(experiment_name)

        os.environ["MLFLOW_S3_ENDPOINT_URL"] = f"http://{minio_host}:{minio_port}"
        os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"

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
            auth=(mlflow_user_username, mlflow_user_password),
            timeout=300,
        )

        assert "1" == r.json()["model_version"]["version"]
        assert "READY" == r.json()["model_version"]["status"]
