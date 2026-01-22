import re
import time

import docker
from testcontainers.compose import DockerCompose


class ExtendedDockerCompose(DockerCompose):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.docker_client = docker.from_env()

    def wait_for_logs(self, service_name, expected_log, timeout=300, interval=5):
        """
        Wait for a specific log entry in the Docker service's logs.

        :param service_name: The name of the service in the Docker Compose file.
        :param expected_log: A string or regex pattern to match in the service logs.
        :param timeout: Maximum time to wait for the log in seconds.
        :param interval: Time interval between log checks in seconds.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            logs = self.get_service_logs(service_name)

            # Use regex to match the expected log pattern
            if re.search(expected_log, logs):
                print(f"Found expected log matching: {expected_log}")
                return

            time.sleep(interval)

        raise TimeoutError(
            f"Log message matching '{expected_log!r}' not found within {timeout} seconds."
        )

    def get_service_logs(self, service_name):
        """
        Fetch logs for a specific service using the Docker SDK.

        :param service_name: The name of the service in the Docker Compose file.
        :return: The logs as a decoded string.
        """
        try:
            containers = self.docker_client.containers.list(filters={"name": service_name})
            if not containers:
                print(
                    f"No container found for service '{service_name!r}'. Probably it's not ready yet."
                )
                return ""

            logs = containers[0].logs().decode("utf-8")
            return logs
        except Exception as e:
            # Explicitly re-raise the exception with additional context
            raise RuntimeError(f"Error fetching logs for service '{service_name!r}': {e}") from e
