FROM python:3.11-slim

# Prevent .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY main.py /app/main.py

RUN pip install --no-cache-dir -r requirements.txt

# Expose the Flask port
EXPOSE 10123

# Run the exporter
CMD ["python", "main.py"]
