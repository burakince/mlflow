# Stage 1: Build and dependencies
FROM python:3.12.10 AS foundation

LABEL maintainer="Burak Ince <burak.ince@linux.org.tr>"

WORKDIR /mlflow-build/

# Copy only necessary files for dependency installation
COPY pyproject.toml poetry.toml poetry.lock LICENSE README.md ./
COPY mlflowstack ./mlflowstack

# Create necessary symlinks
RUN ln -s /usr/bin/dpkg-split /usr/sbin/dpkg-split \
    && ln -s /usr/bin/dpkg-deb /usr/sbin/dpkg-deb \
    && ln -s /bin/rm /usr/sbin/rm \
    && ln -s /bin/tar /usr/sbin/tar

# Install required build tools and libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      make \
      build-essential \
      libssl-dev \
      zlib1g-dev \
      libbz2-dev \
      libreadline-dev \
      libsqlite3-dev \
      wget \
      curl \
      libncursesw5-dev \
      xz-utils \
      tk-dev \
      libxml2-dev \
      libxmlsec1-dev \
      libffi-dev \
      liblzma-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /tmp/* /var/tmp/*

# Upgrade pip and install Poetry with no cache
RUN python -m pip install --upgrade pip --no-cache-dir && \
    pip install poetry wheel --no-cache-dir

# Install project dependencies without development tools
RUN poetry build

WORKDIR /mlflow/

RUN python -m venv .venv && \
    . .venv/bin/activate && \
    pip install /mlflow-build/dist/mlflowstack-1.0-py3-none-any.whl

# Stage 2: Final slim image
FROM python:3.12.10-slim

LABEL maintainer="Burak Ince <burak.ince@linux.org.tr>"

# Create a non-root mlflow user and group
RUN groupadd -r mlflow && useradd -r -g mlflow -m -d /home/mlflow mlflow

WORKDIR /mlflow/

# Set ownership of the mlflow directory to the mlflow user
RUN chown -R mlflow:mlflow /mlflow

# Copy the virtual environment from the foundation stage and set ownership
COPY --from=foundation --chown=mlflow:mlflow /mlflow/.venv /mlflow/.venv

# Set PATH to include the virtual environment
ENV PATH=/mlflow/.venv/bin:$PATH

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER mlflow

# Default command to run MLflow server
CMD ["mlflow", "server", "--backend-store-uri", "sqlite:///mlflow.sqlite", "--default-artifact-root", "./mlruns", "--host=0.0.0.0", "--port=5000"]
