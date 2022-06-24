# https://mcr.microsoft.com/v2/azure-storage/azurite/tags/list
ARG AZURITE_VERSION=3.18.0
ARG AZURE_STORAGE_BLOB_VERSION=12.10.0

FROM mcr.microsoft.com/azure-storage/azurite:${AZURITE_VERSION}

ENV NODE_PATH /usr/local/lib/node_modules

RUN npm install -g @azure/storage-blob@${AZURE_STORAGE_BLOB_VERSION}
