import os

import requests
from azure.storage.blob import BlobServiceClient
from testcontainers.compose import DockerCompose

import mlflow
from mlflow.tracking.client import MlflowClient


def test_postgres_backended_azure_simulation_model_upload_and_access_via_api(
    test_model, training_params, conda_env
):
    with DockerCompose(
        context=".",
        compose_file_name=["docker-compose.azure-postgres-test.yaml"],
        pull=True,
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


def connection_str(host, blob_port, queue_port):
    return (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        f"BlobEndpoint=http://{host}:{blob_port}/devstoreaccount1;"
        f"QueueEndpoint=http://{host}:{queue_port}/devstoreaccount1"
    )
