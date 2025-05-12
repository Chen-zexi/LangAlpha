FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VENV_PATH=/opt/venv \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install uv
RUN python -m ensurepip --upgrade && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uv==0.6.16 # Match version from agent if specified, or use a recent one

# Create a virtual environment
RUN uv venv ${VENV_PATH} --seed

# Activate virtual environment for subsequent RUN instructions
# This is tricky with RUN, usually handled by ensuring uv points to venv pip or prepending to PATH
ENV PATH="${VENV_PATH}/bin:$PATH"

# Copy application code
COPY ./src/valuation /app/valuation

# Copy the requirements file
COPY ./src/valuation/requirements.txt /app/requirements.txt

# Install dependencies using uv into the virtual environment
# Ensure that uv uses the created venv. Since PATH is updated, it should.
RUN uv pip install -r /app/requirements.txt

# Set PYTHONPATH to include the application directory so local modules can be imported
ENV PYTHONPATH="${APP_HOME}:${PYTHONPATH}"

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Assumes main.py is in /app/valuation and contains an ASGI app instance named 'app'
CMD ["uvicorn", "valuation.main:app", "--host", "0.0.0.0", "--port", "8000"] 