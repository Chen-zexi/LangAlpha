FROM langchain/langgraph-api:3.11


ENV PYTHONDONTWRITEBYTECODE=1 \
    VENV_PATH=/opt/venv

WORKDIR /app

RUN python -m ensurepip --upgrade && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uv

RUN uv venv ${VENV_PATH} --seed

COPY src/agent/market_intelligence_agent /app/market_intelligence_agent

# Copy the requirements file
COPY src/agent/requirements.txt /app/requirements.txt

# Install dependencies from requirements.txt instead of editable install
RUN . ${VENV_PATH}/bin/activate && \
    uv pip install -r /app/requirements.txt -c /api/constraints.txt

ENV PATH="${VENV_PATH}/bin:$PATH"
# Add the app directory to PYTHONPATH so the local agent code can be imported
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV LANGSERVE_GRAPHS='{"market_intelligence_agent": "market_intelligence_agent.graph:build_graph"}'
