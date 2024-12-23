# fe/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Cài đặt streamlit
RUN pip install streamlit

# Copy source code
COPY . .

# Expose port
EXPOSE 8501

# Chạy streamlit
CMD ["streamlit", "run", "streamlit/streamlit.py", "--server.port", "9000", "--server.address", "0.0.0.0"]