# Use official lightweight Python image
FROM python:3.11-slim

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first
COPY pyproject.toml ./

# Install project dependencies using uv (no lock file initially needed, uv resolves on the fly)
RUN uv pip install --system --upgrade -r pyproject.toml

# Copy server code
COPY main.py ./

# Cloud Run injects the $PORT environment variable, default to 8080 if not set
ENV PORT=8080
EXPOSE 8080

# Run in SSE/FastAPI mode using the system python with uvicorn
CMD ["python", "main.py", "--transport", "sse", "--port", "8080"]
