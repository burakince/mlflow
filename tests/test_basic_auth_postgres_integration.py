import os
import re

import requests

from .extended_docker_compose import ExtendedDockerCompose

import mlflow
from mlflow.tracking.client import MlflowClient

# from testcontainers.compose import DockerCompose
# from testcontainers.core.waiting_utils import wait_for_logs


def test_postgres_backended_model_upload_and_access_with_basic_auth(
    test_model, training_params, conda_env
):
    with ExtendedDockerCompose(
        context=".",
        compose_file_name=["docker-compose.basic-auth-test.yaml"],
        # pull=True,
        build=True,
    ) as compose:
        mlflow_host = compose.get_service_host("mlflow", 8080)
        mlflow_port = compose.get_service_port("mlflow", 8080)
        minio_host = compose.get_service_host("minio", 9000)
        minio_port = compose.get_service_port("minio", 9000)

        admin_username = "testuser"
        admin_password = "simpletestpassword"

        base_url = f"http://{mlflow_host}:{mlflow_port}"

        log_message = f".*Listening at: {re.escape(base_url)}.*"
        compose.wait_for_logs("mlflow", log_message)

        experiment_name = "aws-cloud-postgres-experiment"
        model_name = "test-aws-pg-model"
        stage_name = "Staging"
        os.environ["MLFLOW_TRACKING_USERNAME"] = admin_username
        os.environ["MLFLOW_TRACKING_PASSWORD"] = admin_password

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

            client = MlflowClient()
            client.set_registered_model_alias(
                name=model_details.name,
                alias=stage_name,
                version=model_details.version,
            )

        params = {"name": model_name, "alias": stage_name}
        latest_version_url = f"{base_url}/api/2.0/mlflow/registered-models/alias"
        r = requests.get(
            url=latest_version_url,
            params=params,
            auth=(admin_username, admin_password),
            timeout=300,
        )

        assert "1" == r.json()["model_version"]["version"]
        assert "READY" == r.json()["model_version"]["status"]
