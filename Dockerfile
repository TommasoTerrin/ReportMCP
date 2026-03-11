# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Ensure fastmcp supports SSE/HTTP app mounting (should be in >=2.0.0 or similar)
# If fastmcp needs uvicorn or starlette, they are in requirements.txt

# Copy project files
COPY . .

# Create directory for persistent data
RUN mkdir -p /app/data

# Cleanup scripts directory (not needed anymore)
RUN rm -rf scripts

# Expose only the main application port
EXPOSE 8050

# Run the unified application
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8050"]
