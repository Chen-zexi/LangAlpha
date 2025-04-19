# Product Requirements Document: LangAlpha

**Version:** 1.0
**Date:** 2025-04-18
**Status:** Draft

## 1. Introduction

LangAlpha is a multi-agent AI equity analysis tool designed to provide comprehensive insights into the stock market. It leverages Large Language Models (LLMs) and agentic workflows, primarily through LangGraph, to automate data gathering, processing, and analysis, aiming to generate actionable investment signals and support user-driven research through a natural language interface.

## 2. Goals

*   **Automate Equity Analysis:** Reduce manual effort in gathering and processing financial data and news via an intelligent agent workflow.
*   **Provide Comprehensive Insights:** Offer multi-faceted analysis incorporating fundamental, technical, macroeconomic, and sentiment factors.
*   **Generate Investment Signals:** (Future Goal) Employ various agent-driven strategies to identify potential trading opportunities.
*   **Support User Research:** Enable users to ask complex questions about stocks and markets in natural language and receive synthesized answers derived from an agentic process.
*   **Integrate Valuation Models:** (Future Goal) Provide robust valuation capabilities based on established methodologies (e.g., Damodaran).

## 3. Target Audience

*   Retail Investors seeking automated analysis tools.
*   Financial Analysts looking to augment their research workflow.
*   Portfolio Managers needing quick insights and signal generation.
*   Students and Researchers in finance and AI.

## 4. Features

### 4.1. LLM Agent-Driven Analysis Tool (Market Intelligence Agent - **Primary Focus**)
*   **Core Component:** This is the central, actively developed feature residing in `src/agent/market_intelligence_agent/`. It utilizes a LangGraph state machine to orchestrate a team of specialized agents for research and analysis.
*   **Natural Language Query Interface:** Accepts user questions about stocks, markets, or economic events as the initial input.
*   **Autonomous Agent Workflow (LangGraph Implementation):**
    *   **State Management:** Uses a defined `State` (`graph/types.py`) to pass information (messages, plan, configuration) between nodes.
    *   **Nodes (`graph/nodes.py`):**
        *   `coordinator_node`: Entry point. Communicates with the user (simulated) and decides whether to initiate planning or end the process.
        *   `planner_node`: Generates a step-by-step plan (expected as JSON) to address the user query. Can optionally perform a web search (`Tavily`) before planning if configured. Supports different LLMs ("basic", "reasoning") based on a `deep_thinking_mode` flag.
        *   `supervisor_node`: Central router. Receives the plan and delegates tasks to other agents based on the current state and plan. Uses a structured output LLM call (`Router` schema) to determine the next agent (`researcher`, `coder`, `reporter`) or end the workflow (`FINISH`).
        *   `research_node`: Executes research tasks, likely using integrated tools (e.g., Tavily web search). Invokes the research agent defined in `agents/get_research_agent()`.
        *   `code_node`: Executes Python code snippets as part of the analysis. Invokes the coder agent defined in `agents/get_coder_agent()`.
        *   `reporter_node`: Compiles the final report or synthesis based on the gathered information and completed tasks.
    *   **Edges (`graph/builder.py`):** Defines the flow: `START` -> `coordinator` -> (`planner` | `__end__`) -> `supervisor` <-> (`researcher` | `coder` | `reporter`) -> `supervisor` -> `__end__`. This indicates a loop where the supervisor delegates tasks iteratively until the plan is complete.
*   **Tool Integration:** Currently integrates the Tavily web search tool (`tools/tavily.py`). Other tools can be added to the agents (Researcher, Coder).

### 4.2. LLM Agent-Driven Trading Signal Generation (**Planned / Not Started**)
*   **Concept:** Envisioned as a separate set of specialized LLM agents focused *specifically* on generating investment/trading signals based on various strategies (fundamental, technical, macro, sentiment).
*   **Status:** This component is **not yet developed**. It is planned for future implementation, potentially running parallel to or after further development of the Market Intelligence Agent.
*   **Integration:** Expected to be callable as a tool by the main Analysis Tool or run independently.

### 4.3. Damodaran Valuation Model (`models/`) (**Planned / Underdeveloped**)
*   **Concept:** Intended to implement valuation methodologies inspired by Professor Aswath Damodaran.
*   **Status:** This component is **underdeveloped** and **not a primary focus** currently. The `models/` directory exists, but functional implementation and integration are pending.
*   **Interfaces (Planned):**
    *   Manual UI (Details TBD).
    *   Callable Tool Interface for the Market Intelligence Agent.

### 4.4. Data Management (`data/`, `src/data_tool/`, `src/database_tool/`)
*   **Data Sources:** Configuration allows for connecting to Polygon, Yahoo Finance, WRDS, and potentially custom MCP integrations. 
*   **Data Retrieval Tools (`src/data_tool/data_providers`):** Contains modules for fetching data from various providers (`polygon.py`, `yahoo_finance.py`, `financial_datasets.py`, `connect_wrds.py`) and standardized Pydantic models (`data_models.py`).
    *   **Status:** **Many of these tools (`polygon`, `yahoo_finance`, `financial_datasets`, `wrds`) are currently *not integrated* into the primary Market Intelligence Agent workflow.** They represent potential data sources to be incorporated as tools for the agents (e.g., Researcher).
*   **Database (`src/database_tool/`):** Contains scripts for MySQL connection (`connect_db.py`), schema creation (`create_table.py`), and potential complex queries (`db_operation.py`).
    *   **Status:** The database infrastructure exists but is **not actively leveraged** within the main agent pipeline currently. It could be used for caching results, storing historical data, or user information in the future.
*   **LLM Configuration (`src/llm/`):** Provides centralized LLM model definitions (`llm_models.py`) and direct API call utilities (`api_call.py`) for potential use outside the main LangGraph workflow.

## 5. System Architecture

*   **Core Framework:** LangGraph manages the primary Market Intelligence Agent workflow, defining states, nodes (agents/functions), and edges (transitions). LangChain is used for agent creation and LLM interactions within nodes.
*   **Primary Workflow (Market Intelligence Agent):** The system operates as a multi-agent collaboration orchestrated by LangGraph: Coordinator assesses the query, Planner creates a strategy, Supervisor delegates tasks (research, coding, reporting) iteratively based on the plan, and agents execute their specialized functions, passing results back through the shared state until the Supervisor determines completion.
*   **Modularity:** Code is organized into components (agents, graph, tools, data_tool, database_tool, models, llm), facilitating future expansion and maintenance.
*   **Tooling:** Agents (primarily Researcher and Coder) leverage specific tools (currently Tavily search) to interact with external resources or perform actions. The architecture supports adding more tools.
*   **Data Flow:** User Query -> Coordinator -> Planner -> Supervisor -> (Research/Code/Report Nodes + Tools) -> Supervisor -> Reporter -> Final Output. Data (user input, intermediate results, plan, final report) is passed via the LangGraph `State`.
*   **Persistence:** Currently limited; MySQL database (`src/database_tool/`) is available but not integrated into the main flow.

**(See `assets/graph.jpg` in the repository for a high-level visual representation, though the detailed flow is described above).**

## 6. Technology Stack

*   **Programming Language:** Python
*   **AI/LLM Frameworks:** LangGraph, LangChain
*   **Data Access:** Tavily Search API (integrated). Polygon API, Yahoo Finance API, WRDS API (available in `src/data_tool/` but not integrated), Web Crawlers.
*   **Database:** MySQL (available via `src/database_tool/` but not integrated).
*   **Development Environment:** Conda
*   **Key Libraries:** Pydantic (for data modeling in `src/data_tool/`), Logging.

## 7. Non-Functional Requirements (Initial Thoughts)

*   **Reliability:** Robust error handling within agent nodes and tool executions.
*   **Scalability:** Consider efficiency of LLM calls and potential for parallel execution within the graph.
*   **Maintainability:** Clear code structure, comments, adherence to modular design.
*   **Accuracy:** Validate tool outputs and agent reasoning where possible.
*   **Security:** Secure management of API keys (e.g., via `.env`).
*   **Observability:** Enhanced logging (currently uses Python `logging`) and potential integration with LangSmith for tracing.

## 8. Future Considerations / Roadmap (**Short-Term Focus: Market Intelligence Agent Enhancement**)

1.  **Tool Integration (MCP Focus):**
    *   Refactor existing data retrieval logic (e.g., `src/data_tool/data_providers/polygon.py`) into MCP (Multi-Component Processor) compatible tools.
    *   Integrate these new tools (Polygon, Yahoo Finance, etc.) into the `research_node` or potentially a dedicated `data_gathering_node` within the LangGraph workflow.
2.  **LangGraph Complexity Enhancement:**
    *   **Iterative Refinement:** Implement mechanisms for agents (or the Supervisor) to evaluate the quality/completeness of gathered information or generated responses.
    *   **Self-Correction/Re-planning:** Allow the graph to loop back for additional research/coding iterations if the initial results are deemed insufficient by an evaluation step.
    *   **Advanced Analysis Nodes:** Introduce new nodes/agents responsible for more complex analysis or synthesis *after* initial data gathering (e.g., a "FinancialAnalyst" node that interprets data retrieved by the "Researcher").
3.  **Visualization Tool:**
    *   Develop or integrate a tool (likely used by the `code_node` or a new dedicated node) capable of executing code (e.g., Matplotlib, Seaborn) to generate visualizations (charts, graphs) based on the analyzed data.
    *   Determine how to handle visualization output (e.g., saving image files, returning base64 strings).
4.  **Database Integration:** Begin utilizing the MySQL database for caching API calls, storing analysis results, or managing user session data.
5.  **Prompt Engineering:** Continuously refine agent prompts (`src/agent/market_intelligence_agent/prompts/`) for improved accuracy, reliability, and adherence to the desired output format.
6.  **Testing:** Implement more robust unit and integration tests for agent nodes and tools. 