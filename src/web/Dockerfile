FROM python:3.11

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy the web application code (including pyproject.toml)
COPY src/web /app/web

# Copy necessary config from the agent (if still needed)
# Ensure this path is correct relative to your build context (project root)
COPY src/agent/market_intelligence_agent/config /app/agent/market_intelligence_agent/config

# Install the web package as editable using uv
# This reads dependencies from /app/web/pyproject.toml
RUN uv pip install --system --no-cache-dir -e ./web

# Set environment variables
ENV PYTHONPATH=/app
ENV LANGGRAPH_API_URL=http://langgraph-api:8000
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application using the installed package
CMD ["python", "-m", "web.run_server"] 