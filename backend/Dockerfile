FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Hugging Face Spaces runs as user 1000 (non-root)
RUN chown -R 1000:1000 /app

# Expose the port Hugging Face Spaces expects
EXPOSE 7860

# Switch to the non-root user
USER 1000

# Run migrations and start Daphne ASGI server
CMD python manage.py migrate --noinput && daphne -b 0.0.0.0 -p 7860 flux_backend.asgi:application
