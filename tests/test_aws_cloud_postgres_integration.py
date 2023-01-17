import os

import requests
from testcontainers.compose import DockerCompose

import mlflow
from mlflow.tracking.client import MlflowClient


def test_postgres_backended_aws_simulation_model_upload_and_access_via_api(
    test_model, training_params, conda_env
):
    with DockerCompose(
        filepath=".",
        compose_file_name=["docker-compose.aws-postgres-test.yaml"],
        pull=True,
        build=True,
    ) as compose:
        mlflow_host = compose.get_service_host("mlflow", 5000)
        mlflow_port = compose.get_service_port("mlflow", 5000)
        minio_host = compose.get_service_host("minio", 9000)
        minio_port = compose.get_service_port("minio", 9000)

        base_url = f"http://{mlflow_host}:{mlflow_port}"

        compose.wait_for(base_url)

        experiment_name = "aws-cloud-postgres-experiment"
        model_name = "test-aws-pg-model"
        stage_name = "Staging"
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
            client.transition_model_version_stage(
                name=model_details.name,
                version=model_details.version,
                stage=stage_name,
            )

        params = {"name": model_name, "stages": stage_name}
        latest_version_url = f"{base_url}/api/2.0/mlflow/registered-models/get-latest-versions"
        r = requests.get(url=latest_version_url, params=params)

        assert "1" == r.json()["model_versions"][0]["version"]
        assert "READY" == r.json()["model_versions"][0]["status"]
