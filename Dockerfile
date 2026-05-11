# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Build Python Environment
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY . .
# Install dependencies including the package itself
RUN pip install --no-cache-dir .

# Stage 3: Final Image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    API_HOST=0.0.0.0 \
    API_PORT=7101 \
    API_RELOAD=false

WORKDIR /app

# Copy virtualenv and app code
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build /app
# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Create a data directory for persistent volumes
RUN mkdir -p /app/data && \
    useradd --create-home appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 7101

# The main entrypoint starts the FastAPI server using module syntax
ENTRYPOINT ["python", "-m", "api.main"]
