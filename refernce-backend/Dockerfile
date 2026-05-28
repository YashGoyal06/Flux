# Use a lightweight official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to optimize Python execution
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOME=/home/user

# Install system dependencies (build-essential, libpq-dev for PostgreSQL compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user with UID 1000 (Hugging Face Spaces runs as UID 1000)
RUN useradd -m -u 1000 user

# Set up the work directory under the user's home
WORKDIR $HOME/app

# Copy the requirements file and install dependencies
COPY --chown=user:user requirements.txt $HOME/app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY --chown=user:user . $HOME/app/

# Ensure the workdir and home directories are fully owned by the user
RUN chown -R user:user $HOME

# Switch to the non-root user
USER user

# Expose the Hugging Face Spaces default port (7860)
EXPOSE 7860

# Run database migrations and start Daphne ASGI server
CMD ["sh", "-c", "python manage.py migrate && daphne -b 0.0.0.0 -p 7860 hiresync_backend.asgi:application"]
