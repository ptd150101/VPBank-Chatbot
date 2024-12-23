FROM pgvector/pgvector:pg16 as builder

# Install necessary packages and download pg_search
RUN apt-get update && apt-get install -y \
    libicu-dev \
    curl \
    && curl -L -o pg_search.deb https://github.com/paradedb/paradedb/releases/download/v0.11.0/postgresql-16-pg-search_0.11.0-1PARADEDB-bookworm_amd64.deb \
    && dpkg -i pg_search.deb \
    && rm pg_search.deb \
    && apt-get remove -y curl \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create final image
FROM pgvector/pgvector:pg16

# Copy pg_search files from builder
COPY --from=builder /usr/lib/postgresql/16/lib/pg_search.so /usr/lib/postgresql/16/lib/
COPY --from=builder /usr/share/postgresql/16/extension/pg_search* /usr/share/postgresql/16/extension/

# Install libicu
RUN apt-get update && apt-get install -y \
    libicu-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add pg_search to shared_preload_libraries in the default config file
RUN echo "shared_preload_libraries = 'pg_search'" >> /usr/share/postgresql/postgresql.conf.sample

# Set environment variable to disable telemetry
ENV PARADEDB_TELEMETRY=false

# Expose PostgreSQL port
EXPOSE 5432

# Set the entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Set the default command
CMD ["postgres"]

