ARG MINICONDA_VERSION=4.10.3

FROM continuumio/miniconda3:${MINICONDA_VERSION} AS foundation

LABEL maintainer="Burak Ince <burak.ince@linux.org.tr>"

WORKDIR /mlflow/
COPY pyproject.toml poetry.toml poetry.lock /mlflow/

# install build-essential to compile extensions.
RUN apt-get update && \
    apt-get install -y build-essential curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip

RUN pip install poetry wheel &&  \
    poetry install --no-root --no-dev

FROM continuumio/miniconda3:${MINICONDA_VERSION}

WORKDIR /mlflow/

COPY --from=foundation /mlflow /mlflow

ENV PATH=/mlflow/.venv/bin:$PATH

# Tell Python *not* to buffer output. Useful to have "real-time" log output within containers.
ENV PYTHONUNBUFFERED 1

CMD mlflow server --backend-store-uri sqlite:///:memory --default-artifact-root ./mlruns --host=0.0.0.0 --port=5000
