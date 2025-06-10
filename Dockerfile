FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Install required packages
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y python3 python3-pip python3-venv python3-dev ffmpeg sudo python-is-python3 rabbitmq-server

# Copy project into image
WORKDIR /app
COPY . .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Add entrypoint script
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]