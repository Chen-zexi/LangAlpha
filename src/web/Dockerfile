FROM python:3.12

WORKDIR /app

# Copy requirements first for better caching
COPY src/web/requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the web application code - maintain directory structure
COPY src/web /app/web
COPY src/agent/market_intelligence_agent/config /app/agent/market_intelligence_agent/config

# Set environment variables
ENV PYTHONPATH=/app
ENV LANGGRAPH_API_URL=http://langgraph-api:8000
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "web.run_server"] 