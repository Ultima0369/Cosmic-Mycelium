# Cosmic Mycelium — Multi-stage production Dockerfile
# Targets: x86_64, aarch64 (ARM64), riscv64 (future-proof)

# ============================================================================
# Stage 1: Builder — compile Python deps into venv
# ============================================================================
FROM python:3.13-slim-bookworm AS builder

ARG TARGETPLATFORM
ARG BUILDPLATFORM

# System build dependencies (for packages with C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    libffi-dev \
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

# Install Python dependencies into venv (no dev deps for production)
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -e "."

# ============================================================================
# Stage 2: Runtime — minimal production image
# ============================================================================
FROM python:3.13-slim-bookworm AS runtime

ARG UID=10001
ARG GID=10001

# Non-root user
RUN groupadd -g ${GID} mycelium && \
    useradd -u ${UID} -g ${GID} -m -s /bin/bash mycelium

# Runtime system libraries (for numpy/scipy/faiss)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app
RUN mkdir -p /app/data /app/logs && chown -R mycelium:mycelium /app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=mycelium:mycelium cosmic_mycelium/ cosmic_mycelium/
COPY --chown=mycelium:mycelium scripts/ scripts/

# Configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COSMIC_MYCELIUM_ENV=production \
    COSMIC_MYCELIUM_DATA_DIR=/app/data \
    COSMIC_MYCELIUM_LOG_DIR=/app/logs

# Health check — imports succeed and basic infant instantiation works
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from cosmic_mycelium.infant.main import SiliconInfant; SiliconInfant('healthcheck'); print('OK')" || exit 1

# Switch to non-root user
USER mycelium

# Default entrypoint: run a single infant
ENTRYPOINT ["cosmic-infant"]
CMD ["--help"]
