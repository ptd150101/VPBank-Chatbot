# Stage 1: Build dependencies
FROM python:3.10-slim as builder

# Cài đặt build dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    python3-dev \
    libpq-dev

WORKDIR /install

# Cài đặt uv
RUN pip install uv

# Copy và cài đặt requirements
COPY requirements.txt .
RUN uv pip install --system --target=/install "instructor[vertexai]"
RUN uv pip install --system --target=/install -r requirements.txt

# Stage 2: Runtime
FROM huanidz/pgvector_pgsearch:latest

# Cài đặt Python và các dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    git \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages từ stage builder
COPY --from=builder /install /usr/local/lib/python3.10/site-packages/

WORKDIR /app/

# Copy source code
COPY . .

# Tạo script khởi động mới
RUN echo '#!/bin/bash\n\
\n\
# Kiểm tra kết nối tới Railway PostgreSQL\n\
until pg_isready -h junction.proxy.rlwy.net -p 45318 -U postgres; do\n\
  echo "Waiting for Railway PostgreSQL to be ready..."\n\
  sleep 1\n\
done\n\
\n\
# Tạo extensions nếu chưa có\n\
PGPASSWORD=xBIDEotzIbAwwkWNkxGhcKvgYUggyvwF psql -h junction.proxy.rlwy.net -p 45318 -U postgres -d railway -c "CREATE EXTENSION IF NOT EXISTS vector;" || true\n\
PGPASSWORD=xBIDEotzIbAwwkWNkxGhcKvgYUggyvwF psql -h junction.proxy.rlwy.net -p 45318 -U postgres -d railway -c "CREATE EXTENSION IF NOT EXISTS pg_search;" || true\n\
\n\
# Start backend\n\
python3 source/run.py &\n\
\n\
# Start frontend\n\
streamlit run streamlit/streamlit.py --server.port 8501 --server.address 0.0.0.0\n\
\n\
# Keep container running\n\
wait' > start.sh

# Cấp quyền thực thi cho script
RUN chmod +x start.sh

# Expose ports
EXPOSE $PORT
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Chạy script
CMD ["./start.sh"] 