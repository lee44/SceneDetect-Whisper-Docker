# Docker Installation Instructions

## Pull Docker Image

To pull the Docker image from a registry (e.g., Docker Hub), use the following command:

```bash
docker pull scenedetectwhisper:latest
```

## Run Docker Container

To run the Docker container, use the following command:

```bash
docker run --rm --gpus all -e "NVIDIA_DRIVER_CAPABILITIES=all" -e "NVIDIA_VISIBLE_DEVICES=all" -e "FOLDER_1={folder_name}" --runtime=nvidia -v {host_path}:/videos scenedetectwhisper:latest
```

### Explanation:

- `-e "FOLDER_1={folder_name}"`: Replace {folder_name} with the name of the folder. To add more folders, add another environment variable e.g `-e "FOLDER_2={folder_name}"`
