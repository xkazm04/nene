# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install FFmpeg and other system dependencies
# Using --no-install-recommends to keep the image size smaller
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    # Clean up apt caches to reduce image size
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the .env file (if it exists) for environment variables
COPY .env* ./

# Copy the rest of the application code into the container
COPY . .

# Ensure all Python files have proper permissions
RUN chmod +x main.py


# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run uvicorn when the container launches.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]