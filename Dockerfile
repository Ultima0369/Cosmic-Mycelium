# Cosmic Mycelium — Multi-stage production Dockerfile
# Targets: x86_64, aarch64 (ARM64), riscv64 (future-proof)

# ============================================================================
# Stage 1: Builder — compile Rust core (if present) & Python deps
# ============================================================================
FROM python:3.13-slim-bookworm AS builder

# Build args for cross-compilation
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# System build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    libffi-dev \
    rustc \
    cargo \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create virtualenv
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy dependency manifests
WORKDIR /app
COPY pyproject.toml README.md ./
COPY cosmic_mycelium/__init__.py cosmic_mycelium/

# Install Python dependencies (no-cache-dir for smaller layers)
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -e ".[dev,cluster]"

# ============================================================================
# Stage 2: Runtime — minimal production image
# ============================================================================
FROM python:3.13-slim-bookworm AS runtime

# Non-root user for security
ARG UID=10001
ARG GID=10001
RUN groupadd -g ${GID} mycelium && \
    useradd -u ${UID} -g ${GID} -m -s /bin/bash mycelium

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    # System libraries for numpy/scipy
    libgomp1 \
    # For OpenBLAS acceleration
    libopenblas-dev \
    # For Redis connectivity (if used)
    redis-tools \
    # For Kafka connectivity (if used)
    librdkafka-dev \
    # Useful tools
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app directories
WORKDIR /app
RUN mkdir -p /app/data /app/logs /app/checkpoints && \
    chown -R mycelium:mycelium /app

# Copy application code
COPY --chown=mycelium:mycelium cosmic_mycelium/ cosmic_mycelium/
COPY --chown=mycelium:mycelium scripts/ scripts/
COPY --chown=mycelium:mycelium tests/ tests/

# Configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COSMIC_MYCELIUM_ENV=production \
    COSMIC_MYCELIUM_DATA_DIR=/app/data \
    COSMIC_MYCELIUM_LOG_DIR=/app/logs

# Health check — validates the infant module can be imported
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from cosmic_mycelium.infant.main import SiliconInfant; print('OK')" || exit 1

# Switch to non-root user
USER mycelium

# Default: print version
CMD ["python", "-c", "from cosmic_mycelium import __version__; print(f'Cosmic Mycelium v{__version__}')"]
