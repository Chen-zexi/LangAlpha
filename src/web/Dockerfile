FROM python:3.11

WORKDIR /app

# Install Node.js and npm
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy the web application code
COPY src/web /app/web

# Copy necessary config from the agent
COPY src/agent/market_intelligence_agent/config /app/agent/market_intelligence_agent/config

# Install the web package as editable using uv
RUN uv pip install --system --no-cache-dir -e ./web

# Set up Tailwind CSS
WORKDIR /app/web
RUN mkdir -p /app/web/static/css
# Initialize package.json
RUN npm init -y
# Install tailwindcss and create config file
RUN npm install --save-dev tailwindcss
# Update browserslist database
RUN npx update-browserslist-db@latest
RUN ./node_modules/.bin/tailwindcss init

# Create a CSS file for Tailwind if it doesn't exist
RUN echo "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\n/* Custom styles */" > /app/web/static/css/input.css

# Build Tailwind CSS at build time for initial version
RUN ./node_modules/.bin/tailwindcss -i /app/web/static/css/input.css -o /app/web/static/css/output.css

WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV LANGGRAPH_API_URL=http://langgraph-api:8000
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application with Tailwind in watch mode for development
CMD ["sh", "-c", "cd /app/web && ./node_modules/.bin/tailwindcss -i ./static/css/input.css -o ./static/css/output.css && python -m web.run_server"] 