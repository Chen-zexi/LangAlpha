FROM python:3.11

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy the web application code
COPY src/web /app/web

# Copy necessary config from the agent
COPY src/agent/market_intelligence_agent/config /app/agent/market_intelligence_agent/config

# Install the web package as editable using uv
RUN uv pip install --system --no-cache-dir -e ./web

# Set environment variables
ENV PYTHONPATH=/app
ENV LANGGRAPH_API_URL=http://langgraph-api:8000
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "web.run_server"] 