import os
import re
import time

import pytest
import requests

import mlflow
from mlflow.server.auth.client import AuthServiceClient
from mlflow.tracking.client import MlflowClient

from .extended_docker_compose import ExtendedDockerCompose


def test_ldap_backended_model_upload_and_access_with_basic_auth(
    test_model, training_params, conda_env
):
    # https://stackoverflow.com/questions/45873832/how-do-i-create-and-sign-certificates-with-pythons-pyopenssl
    # https://stackoverflow.com/questions/27164354/create-a-self-signed-x509-certificate-in-python
    # https://gist.github.com/major/8ac9f98ae8b07f46b208
    # https://gist.github.com/Zeerg/0b0313d22124d3e8b478
    # https://nachtimwald.com/2019/11/14/python-self-signed-cert-gen/
    # https://mikail-eliyah.medium.com/openssl-in-python-keys-and-certificates-e304df79ee0f
    # https://cryptography.io/en/latest/x509/tutorial/
    # https://arminreiter.com/2022/01/create-your-own-certificate-authority-ca-using-openssl/
    # https://www.programcreek.com/python/example/102792/cryptography.x509.CertificateBuilder

    # https://ldap3.readthedocs.io/en/latest/ssltls.html

    # openssl x509 -noout -text -in <cert file>
    # openssl rsa -noout -text -in <key file>
    # openssl req -noout -text -in <csr file>



    with ExtendedDockerCompose(
        context=".",
        compose_file_name=["docker-compose.basic-auth-ldap-ssl-test.yaml"],
        # pull=True,
        build=True,
    ) as compose:
        mlflow_host = compose.get_service_host("mlflow", 8080)
        mlflow_port = compose.get_service_port("mlflow", 8080)
        minio_host = compose.get_service_host("minio", 9000)
        minio_port = compose.get_service_port("minio", 9000)

        mlflow_admin_username = "admin1"
        mlflow_admin_password = "admin1-1234"

        mlflow_user_username = "user1"
        mlflow_user_password = "user1-1234"

        base_url = f"http://{mlflow_host}:{mlflow_port}"

        log_message = f".*Listening at: {re.escape(base_url)}.*"
        compose.wait_for_logs("mlflow", log_message)
        compose.wait_for_logs("mlflow", ".*8606fa83a998, initial_migration")
        time.sleep(5)  # Wait 5 seconds more the get flask ready

        experiment_name = "basic-auth-ldap-experiment"
        model_name = "test-basic-auth-ldap-model"
        stage_name = "Staging"
        os.environ["MLFLOW_TRACKING_USERNAME"] = mlflow_admin_username
        os.environ["MLFLOW_TRACKING_PASSWORD"] = mlflow_admin_password

        mlflow_auth_client = AuthServiceClient(base_url)

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

        compose.stop()
