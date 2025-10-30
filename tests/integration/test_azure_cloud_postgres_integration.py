import os

import requests
import pytest
from azure.storage.blob import BlobServiceClient
from testcontainers.compose import DockerCompose

import mlflow
from mlflow import MlflowClient


@pytest.mark.parametrize("distro", ["debian", "alpine"])
def test_postgres_backended_azure_simulation_model_upload_and_access_via_api(
    distro, test_model, training_params, conda_env
):
    os.environ["DISTRO"] = distro

    with DockerCompose(
        context=".",
        compose_file_name=["docker-compose.azure-postgres-test.yaml"],
        build=True,
    ) as compose:
        mlflow_host = compose.get_service_host("mlflow", 8080)
        mlflow_port = compose.get_service_port("mlflow", 8080)
        azurite_host = compose.get_service_host("azurite", 10000)
        azurite_blob_port = compose.get_service_port("azurite", 10000)
        azurite_queue_port = compose.get_service_port("azurite", 10001)

        base_url = f"http://{mlflow_host}:{mlflow_port}"

        compose.wait_for(base_url)

        experiment_name = "azure-cloud-postgres-experiment"
        model_name = "test-azure-pg-model"
        stage_name = "Staging"
        mlflow.set_tracking_uri(base_url)
        mlflow.set_experiment(experiment_name)
        experiment = mlflow.get_experiment_by_name(experiment_name)
        os.environ["AZURE_STORAGE_CONNECTION_STRING"] = connection_str(
            azurite_host, azurite_blob_port, azurite_queue_port
        )

        blob_service_client = BlobServiceClient.from_connection_string(
            os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        )
        os.environ["STORAGE_CONTAINER"] = "mlflow"

        # Create a container for Azurite for the first run
        blob_service_client = BlobServiceClient.from_connection_string(
            os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        )
        try:
            blob_service_client.create_container(os.environ.get("STORAGE_CONTAINER"))
        except Exception as e:
            print(e)

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
        r = requests.get(url=latest_version_url, params=params, timeout=300)

        assert model_name == r.json()["model_version"]["name"]
        assert "1" == r.json()["model_version"]["version"]
        assert "READY" == r.json()["model_version"]["status"]
        assert "Staging" == r.json()["model_version"]["aliases"][0]


def connection_str(host, blob_port, queue_port):
    return (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        f"BlobEndpoint=http://{host}:{blob_port}/devstoreaccount1;"
        f"QueueEndpoint=http://{host}:{queue_port}/devstoreaccount1"
    )
