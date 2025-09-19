FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies for psycopg2 and others
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Run the app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]