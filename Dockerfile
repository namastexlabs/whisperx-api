FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8880

# Default environment
ENV MURMURAI_HOST=0.0.0.0
ENV MURMURAI_PORT=8880
ENV MURMURAI_DATA_DIR=/app/data

CMD ["murmurai"]
