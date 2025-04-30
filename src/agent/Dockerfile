FROM langchain/langgraph-api:3.11

# -- Adding non-package dependency agent --
ADD . /deps/__outer_agent/agent
RUN set -ex && \
    for line in '[project]' \
                'name = "agent"' \
                'version = "0.1"' \
                '[tool.setuptools.package-data]' \
                '"*" = ["**/*"]'; do \
        echo "$line" >> /deps/__outer_agent/pyproject.toml; \
    done
# -- End of non-package dependency agent --

# Install requirements from requirements.txt
COPY requirements.txt /deps/__outer_agent/agent/
RUN pip install --no-cache-dir -r /deps/__outer_agent/agent/requirements.txt

# -- Installing all local dependencies --
RUN PYTHONDONTWRITEBYTECODE=1 pip install --no-cache-dir -c /api/constraints.txt -e /deps/*
# -- End of local dependencies install --
ENV LANGSERVE_GRAPHS='{"market_intelligence_agent": "market_intelligence_agent.graph:build_graph"}'

WORKDIR /deps/__outer_agent/agent