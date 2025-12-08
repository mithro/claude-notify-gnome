# docker/claude-test/Dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python, systemd support, D-Bus, and build dependencies
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    curl \
    dbus \
    dbus-user-session \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    libgirepository-2.0-dev \
    libdbus-1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY tests/ ./tests/

# Install project with dependencies
RUN uv sync --extra daemon --extra dev

# Create test user
RUN useradd -m -s /bin/bash testuser && \
    mkdir -p /home/testuser/.claude && \
    chown -R testuser:testuser /home/testuser /app

USER testuser
ENV HOME=/home/testuser

ENTRYPOINT ["/app/docker/claude-test/entrypoint.sh"]
CMD ["pytest", "tests/", "-v", "--ignore=tests/e2e/"]
