FROM mongo:latest

# Create a directory for database files
RUN mkdir -p /data/db

# MongoDB port
EXPOSE 27017

# Set recommended MongoDB settings for containerized deployments
ENV MONGO_INITDB_ROOT_USERNAME=admin
ENV MONGO_INITDB_ROOT_PASSWORD=password

# Health check
HEALTHCHECK --interval=5s --timeout=3s --retries=3 \
  CMD mongosh --quiet --eval 'db.runCommand("ping").ok' || exit 1

CMD ["mongod"] 