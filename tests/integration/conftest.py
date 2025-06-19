from sys import version_info

import cloudpickle
import pytest

import mlflow

PYTHON_VERSION = f"{version_info.major}.{version_info.minor}.{version_info.micro}"


class TestModel(mlflow.pyfunc.PythonModel):
    def __init__(self, value):
        self.value = value
        super().__init__()

    def predict(self, context, model_input):
        return "Hello World"


@pytest.fixture
def training_params():
    return {"value": 5}


@pytest.fixture
def test_model(training_params):
    return TestModel(**training_params)


@pytest.fixture
def conda_env():
    return {
        "channels": ["defaults", "conda-forge"],
        "dependencies": [f"python={PYTHON_VERSION}", "pip"],
        "pip": [
            "mlflow",
            f"cloudpickle=={cloudpickle.__version__}",
        ],
        "name": "mlflow-env",
    }
