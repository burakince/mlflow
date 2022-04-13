const { BlobServiceClient, StorageSharedKeyCredential } = require("@azure/storage-blob");

const accountName = process.env.AZURE_STORAGE_ACCOUNT || "";
const accountKey = process.env.AZURE_STORAGE_ACCESS_KEY || "";
const commaSeparatedContainerNames = process.env.COMMA_SEPARATED_CONTAINER_NAMES || "mlflow";

async function createContainer(containerName) {
    const sharedKeyCredential = new StorageSharedKeyCredential(accountName, accountKey);

    const blobServiceClient = new BlobServiceClient(
        `http://localhost:10000/${accountName}`,
        sharedKeyCredential
    );

    const containerClient = blobServiceClient.getContainerClient(containerName);

    const createContainerResponse = await containerClient.create();
    console.log(`Create container ${containerName} successfully`, createContainerResponse.requestId);
}

function main() {
    // const containerNames = commaSeparatedContainerNames.split(",").map(item => item.trim()).filter(item => item !== '');
    const containerNames = [`mlflow`]
    for (var i = 0; i < containerNames.length; i++) {
        const containerName = containerNames[i]
        createContainer(containerName).catch((err) => {
            console.error(`Error running ${containerName}:`, err);
        });
    }
}

main();
