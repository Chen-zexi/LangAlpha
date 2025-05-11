# LangAlpha

## Table of Contents
- [Key Technologies](#key-technologies)
- [Core Functionality: Market Intelligence Agent Workflow](#core-functionality-market-intelligence-agent-workflow)
- [Damodaran Valuation Model](#damodaran-valuation-model)
- [Trading Strategy](#trading-strategy)
- [Repository Structure](#repository-structure)
- [Example Analysis](#example-analysis)
- [General Guide for Usage](#general-guide-for-usage)
  - [How to get better result](#how-to-get-better-result)
  - [What LangAlpha Does Well](#what-langalpha-does-well)
  - [Limitations to Keep in Mind](#limitations-to-keep-in-mind)
- [Getting Started](#getting-started)
  - [Clone the Repository](#1-clone-the-repository)
  - [Docker Setup with Web UI (Recommended)](#2-docker-setup-with-web-ui-recommended)
  - [Manual Setup without Web UI and Docker](#manual-setup-without-web-ui-and-docker)
    - [Environment Setup](#1-environment-setup)
    - [Run the Application](#2-run-the-application)
- [Contributors and contributions](#contributors-and-contributions)
- [Acknowledgements](#acknowledgements)
- [Citation](#citation)

 **Note**: Stocksflags is now renamed to LangAlpha
 
LangAlpha is a multi-agent AI equity analysis tool designed to provide comprehensive insights into the stock market. It leverages Large Language Models (LLMs) and agentic workflows to automate data gathering, processing, and analysis.

## Key Technologies

*   **Programming Language:** Python
*   **AI/LLM Frameworks:** LangChain, LangGraph
*   **Core Agent Workflow:** Implemented in `src/agent/market_intelligence_agent` using LangGraph
*   **Data Sources & Tools:**
    *   **Market/Fundamental Data:** Polygon, Yahoo Finance (via `tools/market_data.py`, `tools/fundamental_data.py`)
    *   **News/Web Research:** Tavily Search, Tickertick News API (via `tools/tavily.py`, `tools/tickertick.py`)
    *   **Web Browsing:** Playwright (integrated via `browser` agent)
    *   **Code Execution:** Local Python/Bash environment (via `coder` agent)
    *   **Database:** We use mongoDB to store the query history and the analysis result in production phase
*   **Environment Management:** `uv`

## Core Functionality: Market Intelligence Agent Workflow

The primary functionality is delivered through a sophisticated **multi-agent system** built with **LangGraph**, located in `src/agent/market_intelligence_agent/`.

**Workflow Overview:**

1.  **User Query:** The system accepts natural language queries about financial markets, stocks, or economic events.
2.  **Supervisor & Planner:** A `supervisor` agent oversees the entire process. It first consults a `planner` agent, which breaks down the user's request into a detailed, step-by-step research and analysis plan.
3.  **Information Gathering (Parallel & Iterative):**
    *   The `supervisor` delegates tasks based on the plan to specialized agents:
        *   **`researcher`:** Fetches news (Tickertick) and performs general web searches (Tavily) for qualitative information, recent events, and context.
        *   **`market`:** Retrieves quantitative data like stock prices, technical indicators, fundamental data (financials, valuation), and related metrics using dedicated tools connected to Polygon and Yahoo Finance.
        *   **`browser`:** (Used sparingly due to cost) Performs deep web browsing for specific, hard-to-find information on given URLs when the `researcher`'s tools are insufficient.
4.  **Analysis & Synthesis:**
    *   **`coder`:** (If required by the plan) Executes Python code for complex calculations, data manipulation, or analysis beyond the `market` agent's built-in capabilities.
    *   **`analyst`:** Acts as a financial expert (L/S Hedge Fund perspective). It synthesizes the information gathered by all other agents, identifies key insights, assesses risks, generates potential investment theses (Long/Short), and provides actionable financial analysis based *only* on the provided data.
5.  **Reporting:**
    *   The `supervisor` reviews the findings from all agents, potentially iterating or requesting clarifications.
    *   Finally, a `reporter` agent compiles all the validated information and analysis into a comprehensive, well-structured Markdown report, including tables and summaries.

**Key Capabilities:**

*   **Autonomous Research:** Agents collaboratively gather diverse data types (news, market data, fundamentals, web content).
*   **In-depth Analysis:** Combines quantitative data retrieval with qualitative research and expert financial analysis.
*   **Structured Planning:** Ensures a logical flow of information gathering and analysis tailored to the user's query.
*   **Flexible Orchestration:** The `supervisor` dynamically routes tasks and manages the workflow, allowing for iteration and refinement.
*   **Actionable Insights:** Aims to provide not just data, but synthesized analysis suitable for investment decision-making context (though not direct financial advice).

Below is an image demonstrate the current agent workflow
![graph](/assets/graph.png)

## Damodaran Valuation Model:
- Implements valuation methodologies inspired by Professor Aswath Damodaran.
- Provides a user interface (details TBD) for manual input and valuation generation.
- See [notebooks/ginzu_interface.ipynb](notebooks/ginzu_interface.ipynb) for details.

## Trading Strategy:
- See [counter-trend-trading-strategy colab](https://colab.research.google.com/drive/1Wo1f5SvZ3M9YjUx7gl4q2rSIo7PMegBN?usp=sharing#scrollTo=1kA-HcwGkK9Z) for details.

## Repository Structure
```
LangAlpha/
├── data                                  # Data directory
├── models                                # Valuation Model directory
├── notebooks/                            # Jupyter notebooks for demonstration               
├── src/                                    # Source code
|    ├── agent/                           # Agent directory
|    |    └── market_intelligence_agent/    # Market Intelligence Agent
|    |         ├── agents/                  # Agent implementations
|    |         ├── prompts/                 # Agent prompts
|    |         ├── tools/                   # Agent tools
|    |         ├── config/                  # Configuration files
|    |         ├── graph/                   # Agent workflow graphs
|    |         ├── service/                 # Service implementations
|    |         ├── crawler/                 # Web crawlers
|    |         └── __init__.py              # Package initialization
|    ├── database/                         # Database setup and utilities
|    |    ├── models/                       # Database models/schemas
|    |    ├── utils/                        # Database utility functions
|    |    └── Dockerfile                    # Dockerfile for database service
|    ├── web/                              # Frontend Web Application (FastAPI)
|    |    ├── static/                       # Static assets (CSS, JS)
|    |    ├── templates/                    # HTML templates
|    |    ├── main.py                       # Main FastAPI application
|    |    └── Dockerfile                    # Dockerfile for web service
|    |
|    └──utlitity/                      # Tools for data retriving
|  
└── ...
```

## Example Analysis

Here are some examples of stock analyses generated by LangAlpha:
- [NVIDIA Year-to-Date Analysis](/assets/nvidia_ytd.md)
- [NVIDIA Two-Month Analysis](/assets/nvidia_two_month.md)
- [Tarrif and Trade War Analysis](/assets/tarrif_and_trade_war.md)
- [Market Summary April 23](/assets/market_summary_april_23.md)
- [Nvidia Report](/assets/nvdia_report.md)
- [Tesla Report](/assets/tesla_report.md)
- [Chinese EV Company Report](/assets/chinese_ev_company_report.md)


Depends on the query, it take 2-6 minutes to generate the response. Token usage is generally around 30000+ to 100000+ tokens. Maxium token usage observed is 490000+ tokens.

Examples are generated in ealier phase of the development. Run the latest version for better result.

## General Guide for Usage:

This guide helps you formulate effective queries when interacting with LangAlpha via the web interface to get the most relevant and comprehensive analysis. LangAlpha uses multiple AI agents working together, so clear instructions lead to better results.

### How to get better result:

1.  **Be Specific About Your Target:**
    *   **Instead of:** "Tell me about the market."
    *   **Ask:** "Provide a market summary for the US stock market for the past week."
    *   **Instead of:** "Analyze Nvidia."
    *   **Ask:** "Analyze Nvidia's stock performance and financial health over the last fiscal year."
    -  You can optionally provide a company to compare with. Specific information (product, service, etc.) you want the report to focus on.

2.  **Define the Scope and Timeframe:**
    *   Specify the period you're interested in (e.g., "last quarter," "year-to-date," "since January 1st, 2024," "the last 5 years").
    *   **Example:** "Summarize the key news affecting the semiconductor industry in the last month."
    *   **Example:** "Compare the YTD stock performance of Ford (F) and General Motors (GM)."

3.  **State Your Desired Outcome:**
    *   What kind of information or analysis do you need?
    *   **News & Events:** "What are the recent major news headlines for Tesla (TSLA)?"
    *   **Financial Data:** "Retrieve the key financial metrics (P/E ratio, EPS, Revenue Growth) for Microsoft (MSFT) for the last two years."
    *   **Technical Analysis:** "Provide a technical analysis of NVIDIA based on daily data for the past 3 months, including RSI and MACD indicators."
    *   **Fundamental Analysis:** "Assess the fundamental strengths and weaknesses of Amazon (AMZN) based on its latest quarterly report."
    *   **Comparative Analysis:** "Compare the valuation metrics of the top 3 cloud computing companies."
    *   **Risk Assessment:** "What are the primary risks associated with investing in Chinese EV stocks right now?"
    *   **Comprehensive Report:** "Generate a comprehensive report on the outlook for the AI cloud service over the next year, including market trends, key players, and potential challenges."

### What LangAlpha Does Well:

*   **Synthesizing Information:** Combining quantitative market data (prices, financials) with qualitative information (news, research).
*   **Structured Analysis:** Breaking down complex requests into logical research and analysis steps.
*   **Generating Reports:** Compiling findings into comprehensive, easy-to-read Markdown reports.
*   **Financial Context:** Providing analysis from a financial perspective

### Limitations to Keep in Mind:

*   **Not Real-Time Trading Advice:** LangAlpha provides analysis based on available data but does not offer live buy/sell recommendations or execute trades.
*   **Data Availability:** Analysis quality depends on the data accessible through its tools (Polygon, Yahoo Finance, Tavily, Tickertick). Highly niche or private data may not be available.
*   **Agent Availability:** Broswer agent is currently not available in the web UI. Try it with the cml version.
*   **Ambiguity:** Very broad or ambiguous queries may lead to less focused or potentially inaccurate results. The clearer your query, the better the outcome.
*   **Scope:** LangAlpha is currently only designed for US stock market analysis. It may not do well on other market or financial instruments.

## Data Accessible by Agent

LangAlpha agents can access the following types of data:

- **Company Fundamentals** (via Alpha Vantage):
  - Company overview (sector, industry, market cap, ratios, etc.)
  - Income statement, balance sheet, cash flow (annual/quarterly)
  - Earnings data (historical EPS, earnings calendar, earnings call transcripts)
- **Advanced Analytics**:
  - Price statistics (min, max, mean, median, stddev, drawdown, correlation, etc.)
- **US Economic Indicators**:
  - GDP, Treasury yields, Fed Funds Rate, CPI, inflation, retail sales, unemployment, payroll, and more
- **Market Data** (via Polygon):
  - OHLCV price data (any US stock, flexible timeframes)
  - Key metrics (price change %, highs/lows, volume, volatility, drawdown, SMA)
  - Real-time ticker snapshots (trade, quote, bar)
  - Market movers (top gainers/losers)
  - Market status (open/closed)
  - Trading signals (trend, mean reversion, momentum, volatility, stat arb, consensus)
- **Financial Modeling Prep Data**:
  - Revenue by product and by geographic region
  - Analyst price target consensus
  - Analyst grades consensus and historical ratings

*All data is fetched live from APIs and subject to availability and API limits.*

## Getting Started

### 1. Clone the Repository
```bash
# Clone the repository to your local machine
git clone https://github.com/Chen-zexi/LangAlpha.git

# Navigate to the project directory
cd LangAlpha
```

### 2. Docker Setup with Web UI (Recommended)

This project is configured to run using Docker Compose, which simplifies the setup of the application, database, and other langraph services.

1.  **Install Docker and Docker Compose:** Ensure you have Docker Desktop (or Docker Engine + Docker Compose) installed on your system. You can download it from the [official Docker website](https://www.docker.com/products/docker-desktop/).

2.  **Configure Environment Variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and replace the placeholder values (`replace_with_your...`) with your actual API keys and database credentials. **Crucially**, ensure the `MONGODB_URI` is set correctly for Docker networking (e.g., `mongodb://admin:password@mongodb:27017/`). The default value in `.env.example` should work if you don't change the service name or credentials in `docker-compose.yml`.

3.  **Build and Run with Docker Compose:**
    *   Navigate to the project's root directory (where `docker-compose.yml` is located).
    *   Run the following command:
        ```bash
        docker-compose up --build -d
        ```
        *   `--build`: Forces Docker Compose to rebuild the images if the Dockerfiles or related source code have changed.
        *   `-d`: Runs the containers in detached mode (in the background).
    *   This command will:
        *   Build the Docker images for the `web`, `database`, and other langraph services specified in `docker-compose.yml`.
        *   Start the containers for all services.
        *   Set up the necessary network connections between the services.

4.  **Access the Application:** Once the containers are running, you should be able to access the web application by navigating to `http://localhost:8000` (or the port specified in `docker-compose.yml` and the web service configuration) in your web browser.
 
    **Note:** Browser is not supported in Web UI. Please use the local version instead.

5.  **Stopping the Application:**
    *   To stop the running containers, navigate to the project root and run:
        ```bash
        docker-compose down
        ```