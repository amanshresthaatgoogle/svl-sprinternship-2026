import os
import google.auth
import google.auth.transport.requests
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag
from google.adk.tools import AgentTool
from .search_agent import search_agent
from .fetch_agent import fetch_agent

load_dotenv()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
INSTANCE_NAME = os.environ.get("GOOGLE_CLOUD_DB_INSTANCE_NAME")
DATABASE_NAME = os.environ.get("DB_NAME")

# ==========================================
# 1. DEFINE BOTTOM-TIER SUBAGENT (DYNAMIC HEATMAP AGENT)
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
    description=(
        "An agent that dynamically queries Cloud SQL to report capacity heatmap colors, find regions/zones "
        "with available capacity for machine types, and check location availability."
    ),
    instruction=(
        "You are an expert Google Cloud capacity advisor with access to a Cloud SQL database.\n\n"
        "### YOUR GOAL:\n"
        "Dynamically generate and execute read-only SQL queries using the `execute_sql_readonly` tool to answer questions "
        "about capacity heatmap colors, region/zone availability, and alternative location options.\n\n"
        "### CLOUD SQL CONNECTION MANDATORY PARAMETERS:\n"
        f"- project: '{PROJECT_ID}'\n"
        f"- instance: '{INSTANCE_NAME}'\n"
        f"- database: '{DATABASE_NAME}'\n\n"
        "### DATABASE SCHEMA (`core_count` table):\n"
        "- `region` (STRING): e.g., 'us-central1', 'us-east1', 'australia-southeast1'\n"
        "- `zone` (STRING): e.g., 'us-central1-a', 'australia-southeast1-c'\n"
        "- `vm_family` (STRING): e.g., 'c4', 'n4', 'c3'\n"
        "- `machine_domain` (STRING): e.g., 'highmem', 'standard', 'lssd'\n"
        "- `percentage_sold` (FLOAT/NUMERIC): Used to calculate color.\n\n"
        "### HEATMAP COLOR CALCULATION LOGIC:\n"
        "Always calculate the color using this `CASE` expression:\n"
        "```sql\n"
        "CASE \n"
        "  WHEN AVG(percentage_sold) IS NULL THEN 'no_data'\n"
        "  WHEN AVG(percentage_sold) < 0.40 THEN 'green'\n"
        "  WHEN AVG(percentage_sold) < 0.70 THEN 'yellow'\n"
        "  WHEN AVG(percentage_sold) <= 0.90 THEN 'red'\n"
        "  ELSE 'very red'\n"
        "END AS color\n"
        "```\n\n"
        "### MACHINE MATCHING CLAUSE:\n"
        "Normalize identifiers by replacing hyphens/spaces with underscores. Use flexible matching in your `WHERE` clause:\n"
        "```sql\n"
        "(\n"
        "  REPLACE(REPLACE(CONCAT(vm_family, '_', machine_domain), '-', '_'), ' ', '_') LIKE '%<identifier>%'\n"
        "  OR REPLACE(machine_domain, ' ', '_') LIKE '%<identifier>%'\n"
        "  OR REPLACE(vm_family, ' ', '_') LIKE '%<identifier>%'\n"
        ")\n"
        "```\n\n"
        "### DYNAMIC QUERY PATTERNS:\n"
        "1. **Checking single location** (e.g., 'c3_standard_lssd in australia-southeast1-c'):\n"
        "   Filter by `region` and `zone` explicitly in the `WHERE` clause.\n"
        "2. **Finding alternative regions** (e.g., 'running out of c4-highmem in us-east1, what other regions have it?'):\n"
        "   - Query `SELECT region, <color_case> FROM core_count WHERE <machine_matching> AND region != 'us-east1' GROUP BY region`.\n"
        "   - Filter or present results showing regions with 'green' or 'yellow' status.\n"
        "3. **Multi-region/All-region heatmap** (e.g., 'heatmap of n4 in all us regions'):\n"
        "   - Query `SELECT region, <color_case> FROM core_count WHERE <machine_matching> AND region LIKE 'us-%' GROUP BY region`.\n\n"
        "### RULES:\n"
        "1. Always pass the mandatory project, instance, and database parameters to `execute_sql_readonly`.\n"
        "2. DO NOT output raw percentage numbers or raw data values to the user. Present ONLY the calculated colors, machine identifier, and region/zone names."
    ),
    tools=[toolkit],
)

# ==========================================
# 2. DEFINE MIDDLE-TIER AGENT (DFO RAG AGENT)
# ==========================================
rag_corpora_string = os.environ["RAG_CORPORA_STRING2"]

dfo_retrieval = VertexAiRagRetrieval(
    name="dfo_vp_tool",
    description="Tool to retrieve documentation on DFO value play strategies, spillover mapping, and capacity remediation guidelines.",
    rag_corpora=[rag_corpora_string],
)

dfo_rag_agent = Agent(
    name="dfo_rag_agent",
    model="gemini-2.5-flash",
    description=(
        "Handles Compute DFO (Demand & Fulfillment Optimization) Value Play inquiries, compute capacity troubleshooting, "
        "alternative machine/region availability lookups, and capacity heatmaps."
    ),
    instruction=(
    "You are an expert Google Cloud DFO (Demand & Fulfillment Optimization) Advisor.\n\n"
    "### ROUTING & TOOL PRIORITY:\n"
    "1. **Capacity, heatmap, or region/zone availability questions** — DELEGATE IMMEDIATELY to `heatmap_agent`. "
    "This is the correct tool for these questions, not a fallback. Do not rely on `dfo_vp_tool` for live capacity data.\n"
    "2. **DFO conceptual & strategy questions** (value play stages, spillover policies, optimization frameworks) — "
    "use `dfo_vp_tool` first.\n"
    "3. **Fallback search** — ONLY if `dfo_vp_tool` lacks the answer, use `search_agent` restricted to site:cloud.google.com.\n"
    "4. **Fetch** — use `fetch_agent` only for the specific documentation URLs it's scoped to.\n"
   "5. **Out of scope (GenAI/Inference)** — for questions on 429 errors, Provisioned Throughput (PT), GSU estimation, "
    "or GenAI models (Gemini/Nano), you MUST transfer control back to `root_agent`. Do not attempt to answer these "
    "yourself, and do not name `genai_vpagent` directly — transfer to your parent, and it will route the query correctly.\n"
    ),
    tools=[dfo_retrieval,
        AgentTool(agent=search_agent),
        AgentTool(agent=fetch_agent),
    ],
    sub_agents=[heatmap_agent],
)