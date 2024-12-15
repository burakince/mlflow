import re
import subprocess
import time

from testcontainers.compose import DockerCompose


class ExtendedDockerCompose(DockerCompose):
    def wait_for_logs(self, service_name, expected_log, timeout=120, interval=5):
        # Get the directory where the compose file is located (context)
        compose_dir = self.context
        compose_files = self.compose_file_name

        if isinstance(compose_files, list):
            compose_file_args = []
            for file in compose_files:
                compose_file_args.extend(["-f", file])
        else:
            compose_file_args = ["-f", compose_files]

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Fetch the logs of the specific service using subprocess
                logs = subprocess.check_output(
                    ["docker-compose", *compose_file_args, "logs", service_name],
                    cwd=compose_dir,  # Use the correct directory
                    text=True,
                )
                # Use regex search to match the expected log pattern
                if re.search(expected_log, logs):
                    print(f"Found expected log matching: {expected_log}")
                    return
            except subprocess.CalledProcessError as e:
                print(f"Error fetching logs: {e}")
            time.sleep(interval)
        raise TimeoutError(
            f"Log message matching '{expected_log!r}' not found within {timeout} seconds."
        )
