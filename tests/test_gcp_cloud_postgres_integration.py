import os

import requests
from testcontainers.compose import DockerCompose

import mlflow
from mlflow import MlflowClient


def test_postgres_backended_gcp_simulation_model_upload_and_access_via_api(
    test_model, training_params, conda_env
):
    with DockerCompose(
        context=".",
        compose_file_name=["docker-compose.gcp-postgres-test.yaml"],
        # pull=True,
        build=True,
    ) as compose:
        mlflow_host = compose.get_service_host("mlflow", 8080)
        mlflow_port = compose.get_service_port("mlflow", 8080)
        gcs_host = compose.get_service_host("gcs", 4443)
        gcs_port = compose.get_service_port("gcs", 4443)

        base_url = f"http://{mlflow_host}:{mlflow_port}"

        compose.wait_for(base_url)

        experiment_name = "gcp-cloud-postgres-experiment"
        model_name = "test-gcp-pg-model"
        stage_name = "Staging"
        mlflow.set_tracking_uri(base_url)
        mlflow.set_experiment(experiment_name)
        experiment = mlflow.get_experiment_by_name(experiment_name)

        os.environ["STORAGE_EMULATOR_HOST"] = f"http://{gcs_host}:{gcs_port}"
        os.environ["GOOGLE_CLOUD_PROJECT"] = "mlflow"

        with mlflow.start_run(experiment_id=experiment.experiment_id) as run:
            mlflow.log_params(training_params)
            mlflow.pyfunc.log_model("model", conda_env=conda_env, python_model=test_model)
            model_uri = f"runs:/{run.info.run_id}/model"
            model_details = mlflow.register_model(model_uri, model_name)

            client = MlflowClient(tracking_uri=base_url)
            client.set_registered_model_alias(
                name=model_details.name,
                alias=stage_name,
                version=model_details.version,
            )

        params = {"name": model_name, "alias": stage_name}
        latest_version_url = f"{base_url}/api/2.0/mlflow/registered-models/alias"
        r = requests.get(url=latest_version_url, params=params, timeout=300)

        assert model_name == r.json()["model_version"]["name"]
        assert "1" == r.json()["model_version"]["version"]
        assert "READY" == r.json()["model_version"]["status"]
        assert "Staging" == r.json()["model_version"]["aliases"][0]
