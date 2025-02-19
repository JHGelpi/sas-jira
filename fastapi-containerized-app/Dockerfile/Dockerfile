# Base image
FROM python:3.11-slim

# Working directory
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev gcc python3-dev \
    cron supervisor && \
    apt-get clean

# Requirements
COPY requirements.txt .

# Install dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the source code
COPY . .

# COPY supervisor config file
COPY supervisord.conf /Users/wegelpi/supervisor/conf.d/supervisord.conf

# Ensure cron service is started
RUN touch /var/log/cron.log

# Expose the port
EXPOSE 8000

# Start the application
CMD ["/Users/wegelpi/supervisord", "-c", "/Users/wegelpi/supervisor/conf.d/supervisord.conf"]