import os
import google.auth
import google.auth.transport.requests
from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

# Load from environment variables with sensible fallbacks
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
INSTANCE_NAME = os.environ.get("GOOGLE_CLOUD_DB_INSTANCE_NAME", "your-sql-instance")
DATABASE_NAME = os.environ.get("DB_NAME", "your-database-name")

# 1. Fetch ADC Credentials & Refresh Access Token
credentials, project_id = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
auth_request = google.auth.transport.requests.Request()
credentials.refresh(auth_request)

# 2. Pass Bearer Token in headers to the Remote MCP endpoint
toolkit = MCPToolset(
    connection_params=StreamableHTTPServerParams(
        url="https://sqladmin.googleapis.com/mcp",
        headers={"Authorization": f"Bearer {credentials.token}"},
    ),
    tool_filter=["execute_sql_readonly"],
)

# 3. Agent System Instruction with parameterized target details
root_agent = Agent(
    name="heatmap_agent",
    model="gemini-2.5-flash",
    description="An agent that reports capacity heatmap colors using Cloud SQL.",
    instruction=(
        "You are an expert Google Cloud capacity advisor.\n\n"
        "When asked for a capacity heatmap color, execute a query using the `execute_sql_readonly` tool.\n\n"
        f"### TARGET CLOUD SQL INSTANCE PARAMETERS:\n"
        f"- project: '{PROJECT_ID}'\n"
        f"- instance: '{INSTANCE_NAME}'\n"
        f"- database: '{DATABASE_NAME}'\n\n"
        "### QUERY TEMPLATE:\n"
        "SELECT "
        "  CASE "
        "    WHEN AVG(percentage_sold) IS NULL THEN 'no_data' "
        "    WHEN AVG(percentage_sold) < 0.40 THEN 'green' "
        "    WHEN AVG(percentage_sold) < 0.70 THEN 'yellow' "
        "    WHEN AVG(percentage_sold) <= 0.90 THEN 'red' "
        "    ELSE 'very red' "
        "  END AS color "
        "FROM core_count "
        "WHERE region = '<region>' "
        "  AND ('<zone>' = '' OR zone = '<zone>') "
        "  AND ("
        "    REPLACE(REPLACE(CONCAT(vm_family, '_', machine_domain), '-', '_'), ' ', '_') = '<raw_identifier>' "
        "    OR REPLACE(machine_domain, ' ', '_') = '<raw_identifier>' "
        "    OR REPLACE(vm_family, ' ', '_') = '<raw_identifier>'"
        "  );\n\n"
        "### RULES:\n"
        f"1. Always supply '{PROJECT_ID}' for project, '{INSTANCE_NAME}' for instance, and '{DATABASE_NAME}' for database in tool calls.\n"
        "2. Replace `<region>`, `<zone>`, and `<raw_identifier>` dynamically based on user input.\n"
        "3. If two words are provided for identifier (e.g., 'n2d viperlitepod'), join them with an underscore ('n2d_viperlitepod').\n"
        "4. Absolutely DO NOT output any raw numbers or percentages. Reply ONLY using the color returned, identifier, and location."
    ),
    tools=[toolkit],
)