FROM python:3.11-slim

# Install required packages
RUN pip install kubernetes

# Create app directory
WORKDIR /app

# Copy scheduler code
COPY custom_scheduler.py /app/

# Make sure the script is executable
RUN chmod +x /app/custom_scheduler.py

# Run the scheduler
CMD ["python3", "/app/custom_scheduler.py"]