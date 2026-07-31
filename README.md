# Topology Task Multi-Agent System

This repository contains a multi-agent system built using the Google Agent Development Kit (ADK). The system is designed to intelligently route user queries to specialized sub-agents that handle specific domains, such as capacity planning, Design for Obtainability (DFO), and Generative AI inference operations.

## Architecture

The system utilizes a hierarchical agent architecture:

*   **Coordinator Agent (`root_agent`)**: The main entry point. It evaluates user queries and routes them to the appropriate specialized sub-agent based on intent. It does not answer queries directly.
*   **DFO Agent (`dfo_rag_agent`)**: Specialized in Design for Obtainability. It handles questions about capacity heatmaps, compute capacity, region/zone availability, and spillover strategies.
*   **GenAI Value Play Agent (`genai_vpagent`)**: Specialized in Generative AI inference. It deals with GenAI model queries, rate limiting (429 errors), quota issues, and Provisioned Throughput (PT) estimation.

## Model Context Protocol (MCP) Integration

A key feature of this system is its integration with the **Model Context Protocol (MCP)**. This allows the agents to securely interact with external data sources and APIs to augment their context dynamically. 

For instance, the `dfo_agent` utilizes an MCP Toolset (`MCPToolset`) to connect to external services (such as the Cloud SQL Admin MCP server) to query live, read-only data (e.g., using `execute_sql_readonly`). The system handles authentication securely and dynamically, refreshing Google Cloud OAuth tokens as needed before making MCP requests to ensure uninterrupted access to these resources without hardcoding sensitive credentials in the code.

## Tools & Capabilities

The sub-agents are equipped with various tools to fetch context:
*   **MCP Tools**: For structured data querying against backend databases.
*   **RAG (Retrieval-Augmented Generation)**: For pulling unstructured context related to value plays and strategies.
*   **Search capabilities**: To find up-to-date information dynamically.

## Getting Started

1.  **Environment Setup**: Ensure you have Python installed and create a virtual environment (`.venv`). Install the required dependencies using `pip install -r requirements.txt`.
2.  **Authentication**: Ensure you are authenticated with Google Cloud (e.g., via `gcloud auth application-default login`) to allow the MCP tools and LLM backend to authenticate securely. **Note:** Environment variables and specific project configurations should be set in a `.env` file (not included in version control for security).
3.  **Run the application**: Use the ADK CLI to run the web server:
    ```bash
    cd topology_task
    adk web
    ```
4.  Navigate to the provided local URL to interact with the agent UI.
