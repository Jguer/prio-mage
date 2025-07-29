# Single stage build for prio_mage
FROM python:3-slim AS production

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Create non-root user
RUN groupadd -r prio && useradd -r -g prio prio

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./

# Install dependencies using uv
RUN uv pip install --system --no-cache-dir -r pyproject.toml

# Copy application code
COPY prio_mage/ ./prio_mage/

# Change ownership to non-root user
RUN chown -R prio:prio /app
USER prio

# Set up environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import prio_mage; print('OK')" || exit 1

# Default entrypoint
ENTRYPOINT ["python", "-m", "prio_mage"]
CMD ["--help"] 