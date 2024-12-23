# Dockerfile gộp tất cả các dịch vụ
FROM python:3.10-slim as base

# Cài đặt build dependencies cho backend
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    python3-dev \
    libpq-dev \
    libicu-dev \
    curl \
    supervisor

# Tạo thư mục làm việc
WORKDIR /app

# Cài đặt pip và streamlit
RUN pip install --no-cache-dir streamlit uv

# Copy và cài đặt requirements cho backend
COPY requirements.txt .
RUN pip install --no-cache-dir --system --target=/install "instructor[vertexai]"
RUN pip install --no-cache-dir --system --target=/install -r requirements.txt

# Copy source code cho cả frontend và backend
COPY . .

# Expose port cho frontend và backend
EXPOSE 8501 8499 5432

# Cài đặt pgvector cho database
FROM pgvector/pgvector:pg16 as builder

# Cài đặt pg_search
RUN apt-get update && apt-get install -y \
    curl \
    && curl -L -o pg_search.deb https://github.com/paradedb/paradedb/releases/download/v0.11.0/postgresql-16-pg-search_0.11.0-1PARADEDB-bookworm_amd64.deb \
    && dpkg -i pg_search.deb \
    && rm pg_search.deb \
    && apt-get remove -y curl \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Tạo image cuối cùng cho database
FROM pgvector/pgvector:pg16

# Cài đặt Python, pip và supervisor trong image cuối cùng
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    supervisor \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy pg_search files từ builder
COPY --from=builder /usr/lib/postgresql/16/lib/pg_search.so /usr/lib/postgresql/16/lib/
COPY --from=builder /usr/share/postgresql/16/extension/pg_search* /usr/share/postgresql/16/extension/

# Cài đặt libicu
RUN apt-get update && apt-get install -y \
    libicu-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Thêm pg_search vào shared_preload_libraries trong file cấu hình mặc định
RUN echo "shared_preload_libraries = 'pg_search'" >> /usr/share/postgresql/postgresql.conf.sample

# Thiết lập biến môi trường để vô hiệu hóa telemetry
ENV PARADEDB_TELEMETRY=false

# Thiết lập entrypoint và command cho database
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]

# Tạo file cấu hình cho supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Chạy supervisor
CMD ["/usr/bin/supervisord"]