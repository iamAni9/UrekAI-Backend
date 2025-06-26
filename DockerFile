# 1. Using an official Python runtime as a parent image
FROM python:3.11-slim

# 2. Setting the working directory in the container
WORKDIR /urekaibackend

# 3. Setting environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_WARN_SCRIPT_LOCATION=0

# 4. Copying and installing Python dependencies
# This is done in a separate step to leverage Docker's layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copying application code into the container
COPY ./app /urekaibackend/app
COPY ./scripts /urekaibackend/scripts

# CMD ["sh", "-c", "python scripts/migration.py && gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:10000 'app.main:create_app()' --factory"]

# 7. Copying supervisor configuration
COPY ./supervisord.conf /etc/supervisord.conf

# 8. Running supervisor
CMD ["supervisord", "-c", "/etc/supervisord.conf"]