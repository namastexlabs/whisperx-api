# MurmurAI - GPU-powered transcription
# Using cudnn variant for speaker diarization support (cuDNN 9 required by ctranslate2 >= 4.5.0)
# CUDA 12.8 provides ~7.6% faster performance vs 12.6 (benchmarked 2024-12)
FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python 3.12 + venv
RUN uv python install 3.12 && uv venv /app/.venv --python 3.12

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy project files for reproducible install
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install with frozen lock file (reproducible builds)
RUN uv sync --frozen --no-dev

# Runtime config
RUN mkdir -p /app/data
EXPOSE 8880
ENV MURMURAI_HOST=0.0.0.0
ENV MURMURAI_PORT=8880
ENV MURMURAI_DATA_DIR=/app/data

CMD ["murmurai"]
