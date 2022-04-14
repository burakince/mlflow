from platform import python_version

import cloudpickle
import pytest

import mlflow


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
    test_model = TestModel(**training_params)
    return test_model


@pytest.fixture
def conda_env():
    return {
        "channels": ["defaults", "conda-forge"],
        "dependencies": [
            "python={}".format(python_version()),
            "pip",
            {"pip": ["cloudpickle={}".format(cloudpickle.__version__)]},
        ],
        "name": "mlflow-env",
    }
