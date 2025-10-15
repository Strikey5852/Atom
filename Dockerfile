# Use official Python 3.12 slim image
FROM python:3.12.8-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Expose port for health check (Flask)
EXPOSE 8080

# Run main.py when container starts
CMD ["python", "main.py"]
