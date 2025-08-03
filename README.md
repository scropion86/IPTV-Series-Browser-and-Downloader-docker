# IPTV Downloader

This project provides a Flask application to download IPTV content.

## Setup and Deployment with Docker

Follow these steps to containerize and run the application using Docker.

### Prerequisites

Ensure you have Docker Desktop installed and running on your system.

### 1. Create `requirements.txt`

Create a file named `requirements.txt` in the root directory of your project (alongside `app.py` and `Dockerfile`) with the following content:

```bash
pip install Flask requests urllib3 tqdm aiohttp
```


Once the application is running, open your web browser and go to `http://127.0.0.1:5000/` (or the address displayed in your terminal).

### 4. Caching Data

For optimal performance, it is recommended to cache the series data. On the search page, click the "Process and Cache Data" button to initiate the caching process. This will fetch all series information from your IPTV provider and store it locally.

### 5. Browsing and Downloading

-   **Browse Categories**: On the main page, click on any category to view the series within it.
-   **Search Series**: Use the search bar on the search page to find specific series.
-   **Download Episodes**: From a series detail page, select the season and episode range you wish to download. The download progress will be displayed in real-time.

## Dockerization


### 2. Ensure `Dockerfile` is Correct

Verify that your `Dockerfile` is configured to install the dependencies from `requirements.txt`. The relevant section should look like this:

```dockerfile
# ... existing code ...

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port that the app runs on
EXPOSE 5000

# ... existing code ...
```

### 3. Build the Docker Image

Navigate to the root directory of your project in your terminal (where `Dockerfile` and `app.py` are located) and run one of the following commands to build the Docker image. If one command fails, try the other.

```bash
docker build -t iptv-downloader .
```

OR

```bash
docker buildx build -t iptv-downloader .
```

This command builds a Docker image named `iptv-downloader`.

### 4. Run the Docker Container

Once the image is built, you can run the container. The application requires `BASE_URL`, `USERNAME`, and `PASSWORD` to be passed as environment variables. Replace the placeholder values with your actual credentials.

```bash
docker run -p 5000:5000 -e BASE_URL="YOUR_BASE_URL" -e USERNAME="YOUR_USERNAME" -e PASSWORD="YOUR_PASSWORD" iptv-downloader
```

- `-p 5000:5000`: Maps port 5000 of your host machine to port 5000 inside the container, allowing you to access the Flask application.
- `-e BASE_URL="..."`: Sets the `BASE_URL` environment variable.
- `-e USERNAME="..."`: Sets the `USERNAME` environment variable.
- `-e PASSWORD="..."`: Sets the `PASSWORD` environment variable.

After running the container, the Flask application should be accessible in your web browser at `http://localhost:5000`.