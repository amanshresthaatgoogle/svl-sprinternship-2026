import os
import google.auth
import google.auth.transport.requests
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag

load_dotenv()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
INSTANCE_NAME = os.environ.get("GOOGLE_CLOUD_DB_INSTANCE_NAME")
DATABASE_NAME = os.environ.get("DB_NAME")

# ==========================================
# 1. DEFINE BOTTOM-TIER SUBAGENT FIRST
# ==========================================

credentials, project_id = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
auth_request = google.auth.transport.requests.Request()
credentials.refresh(auth_request)

toolkit = MCPToolset(
    connection_params=StreamableHTTPServerParams(
        url="https://sqladmin.googleapis.com/mcp",
        headers={"Authorization": f"Bearer {credentials.token}"},
    ),
    tool_filter=["execute_sql_readonly"],
)

heatmap_agent = Agent(
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

# ==========================================
# 2. DEFINE MIDDLE-TIER AGENT SECOND
# ==========================================
rag_corpora_string = os.environ["RAG_CORPORA_STRING2"]

dfo_retrieval = VertexAiRagRetrieval(
    name="dfo_vp_tool",
    description="Tool to retrieve details on DFO value play.",
    rag_corpora=[rag_corpora_string],
)

dfo_rag_agent = Agent(
    name="dfo_rag_agent",
    model="gemini-2.5-flash",
    description="An agent that retrieves and explains details on DFO value play.",
    instruction="Answer questions on DFO value play using retrieved documentation.",
    tools=[dfo_retrieval],
    sub_agents=[heatmap_agent]
)