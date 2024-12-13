FROM python:3.12.8 AS foundation

LABEL maintainer="Burak Ince <burak.ince@linux.org.tr>"

WORKDIR /mlflow/
COPY pyproject.toml poetry.toml poetry.lock /mlflow/

RUN ln -s /usr/bin/dpkg-split /usr/sbin/dpkg-split \
    && ln -s /usr/bin/dpkg-deb /usr/sbin/dpkg-deb \
    && ln -s /bin/rm /usr/sbin/rm \
    && ln -s /bin/tar /usr/sbin/tar

# Install build-essential to compile extensions.
RUN apt-get update && \
    apt-get install -y \
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
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/llvm-config-9 /usr/bin/llvm-config

RUN python -m pip install --upgrade pip

RUN pip install poetry wheel &&  \
    poetry install --no-root --no-dev

FROM python:3.12.8-slim

WORKDIR /mlflow/

COPY --from=foundation /mlflow /mlflow

ENV PATH=/mlflow/.venv/bin:$PATH

# Tell Python *not* to buffer output. Useful to have "real-time" log output within containers.
ENV PYTHONUNBUFFERED=1

CMD ["mlflow", "server", "--backend-store-uri", "sqlite:///:memory", "--default-artifact-root", "./mlruns", "--host=0.0.0.0", "--port=5000"]
