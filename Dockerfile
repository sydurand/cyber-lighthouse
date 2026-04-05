FROM python:3.14-slim

WORKDIR /app

# Install build dependencies for native extensions (numpy, scikit-learn, trafilatura)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p cache logs reports static

# Expose dashboard port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default: start the web dashboard
CMD ["python", "server.py"]
