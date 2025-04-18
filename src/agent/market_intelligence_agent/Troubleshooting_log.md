# Troubleshooting LangGraph Agent with MCP Tools

This document explains the issues encountered when integrating `MultiServerMCPClient` tools into a LangGraph agent running via the `langgraph-sdk` and Jupyter, and the final working solution.

## The Problems

We faced two main errors during development:

1.  **`RuntimeError: Attempted to exit cancel scope in a different task than it was entered in`**: This error originates from the `anyio` library, which is used internally by `MultiServerMCPClient` (likely within its `__aenter__` and `__aexit__` methods) to manage asynchronous operations like background server processes. It indicates that the asynchronous task trying to *clean up* the client's resources (exiting the cancel scope via `__aexit__`) was different from the task that *initialized* them (entering the scope via `__aenter__`). This typically happens when an `async context manager`'s entry and exit points are awaited across different tasks or event loop iterations, which can occur within complex frameworks like LangGraph combined with Jupyter's cell execution.

2.  **`TypeError: Object of type <class 'function'> is not JSON serializable`**: This error occurred when attempting to pass the initialized MCP tools (which are LangChain `Tool` objects containing function references) directly into the `input` dictionary of the `langgraph-sdk`'s `client.runs.stream` method. The SDK client needs to serialize the entire input to JSON to send it to the LangGraph backend server, and standard JSON cannot handle Python functions or complex class instances.

## Initial Approaches & Why They Failed

1.  **Context Manager Inside Node (`research_node_async`)**:
    *   **Attempt**: Wrap the agent creation and invocation within `research_node_async` using `async with get_research_agent():` (where `get_research_agent` internally used `async with managed_mcp_tools():`).
    *   **Result**: Led to the `anyio` `RuntimeError`. The LangGraph runner executing the node likely switched tasks between the `__aenter__` (when the node started) and the `__aexit__` (when the node finished but before returning), causing the cancel scope conflict during the MCP client cleanup.

2.  **Context Manager Outside Stream (Notebook Cell)**:
    *   **Attempt**: Wrap the `client.runs.stream(...)` call in the notebook with `async with managed_mcp_tools() as mcp_tools:` and pass `mcp_tools` in the `input` dictionary.
    *   **Result**: Also led to the `anyio` `RuntimeError` during the `__aexit__` phase when the `async with` block finished in the notebook. The interaction between the Jupyter event loop, the LangGraph SDK client's streaming, and the MCP client's `anyio` usage still resulted in the task mismatch for the cancel scope.

3.  **Passing Tools via State (Notebook Cell)**:
    *   **Attempt**: Initialize the MCP client and get tools (`mcp_tools_global`) directly in the notebook cell, then pass `mcp_tools_global` in the `input` dictionary for the stream.
    *   **Result**: Led to the `TypeError: Object of type <class 'function'> is not JSON serializable`. The SDK client could not serialize the `Tool` objects in the input.

## The Solution: Agent-Side Caching

The working solution involves initializing and caching the `MultiServerMCPClient` and the research agent *within the agent execution environment* (`agents.py`) the first time the agent is requested.

1.  **`agents.py` Modification**:
    *   Global variables `_mcp_client_instance` and `_research_agent_instance` were added to the module scope.
    *   The `get_research_agent()` function was modified:
        *   It's now a regular `async def` function (not a context manager).
        *   On the first call, it checks if `_research_agent_instance` is `None`.
        *   If it's `None`, it initializes `_mcp_client_instance` (if also `None`), calls `await _mcp_client_instance.__aenter__()` (to start background tasks), connects to servers, gets the tools, creates the `research_agent` using `create_react_agent` with the obtained tools, and stores both the client and agent instances in the global variables.
        *   On subsequent calls, it simply returns the cached `_research_agent_instance`.

2.  **`nodes.py` Modification**:
    *   The `research_node_async` function now simply calls `agent = await get_research_agent()` to get the (potentially cached) agent instance. It doesn't manage context managers or tools itself.

3.  **Notebook (`langraph_pipeline_demo.ipynb`) Modification**:
    *   The notebook code was simplified to *only* call the `langgraph-sdk` client's `stream` method, passing the necessary serializable inputs (like `TEAM_MEMBERS` and `messages`). It does *not* initialize or pass the MCP tools.

## How This Solves the Problems

*   **Avoids `anyio` Error**: The MCP client's `__aenter__` is called only *once* during the first request within the agent process. Its `__aexit__` is effectively *never called* automatically in this pattern, thus avoiding the task conflict when trying to exit the cancel scope. The client and its background tasks persist for the lifetime of the agent process (or until manually cleaned up).
*   **Avoids `TypeError`**: The non-serializable `Tool` objects are created and live entirely within the agent execution environment (`agents.py`). They are never included in the `input` dictionary passed from the notebook client to the LangGraph backend, so no problematic serialization occurs.

## Caveat: Resource Cleanup

A significant limitation of this caching approach is that the `MultiServerMCPClient`'s cleanup logic (`__aexit__`) is never triggered automatically. This means background processes started by the client (e.g., the Python processes for `tavily.py`, `tickertick.py`) **may remain running** after the graph execution finishes or even after the notebook kernel is stopped. Proper cleanup would require a mechanism to call `await _mcp_client_instance.__aexit__(None, None, None)` when the agent process shuts down, which is not handled by this solution.