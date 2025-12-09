# docker/gnome-test/Dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Full GNOME session stack
RUN apt-get update && apt-get install -y \
    gnome-session \
    gnome-shell \
    gnome-settings-daemon \
    mutter \
    dbus-daemon \
    dbus-x11 \
    dbus-user-session \
    weston \
    ydotool \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    curl \
    sudo \
    # For headless GPU rendering
    libegl1-mesa \
    libgl1-mesa-dri \
    # For screenshots
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY tests/ ./tests/
COPY docker/gnome-test/weston.ini /etc/weston.ini
COPY docker/gnome-test/entrypoint.sh /entrypoint.sh

# Install project
RUN uv sync --extra daemon --extra dev

# Create test user with uinput access for ydotool
RUN useradd -m -s /bin/bash testuser && \
    usermod -aG input testuser && \
    mkdir -p /home/testuser/.claude && \
    chown -R testuser:testuser /home/testuser /app && \
    # Allow testuser to run ydotoold with sudo
    echo "testuser ALL=(ALL) NOPASSWD: /usr/bin/ydotoold" >> /etc/sudoers

RUN chmod +x /entrypoint.sh

USER testuser
ENV HOME=/home/testuser

ENTRYPOINT ["/entrypoint.sh"]
CMD ["pytest", "tests/e2e/test_notifications.py", "-v"]
