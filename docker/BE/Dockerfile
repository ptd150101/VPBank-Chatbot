# be/Dockerfile
FROM python:3.10-slim

# Cài đặt build dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    python3-dev \
    libpq-dev

WORKDIR /app

# Cài đặt uv
RUN pip install uv

# Copy và cài đặt requirements
COPY requirements.txt .
RUN uv pip install --system --target=/install "instructor[vertexai]"
RUN uv pip install --system --target=/install -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8499

# Chạy script
CMD ["python", "source/run.py"]
