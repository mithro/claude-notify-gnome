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
    dbus-x11 \
    dbus-user-session \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    libgirepository-2.0-dev \
    libdbus-1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv system-wide
RUN curl -LsSf https://astral.sh/uv/install.sh | env INSTALLER_NO_MODIFY_PATH=1 sh \
    && mv /root/.local/bin/uv /usr/local/bin/ \
    && mv /root/.local/bin/uvx /usr/local/bin/

# Copy project
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY tests/ ./tests/

# Pre-install dependencies (will be re-installed at runtime if /app is volume-mounted)
RUN uv sync --extra daemon --extra dev

# Create runtime directory for D-Bus
RUN mkdir -p /tmp/runtime-root && chmod 700 /tmp/runtime-root

# Copy entrypoint and make it executable
COPY docker/claude-test/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["pytest", "tests/", "-v", "--ignore=tests/e2e/"]
