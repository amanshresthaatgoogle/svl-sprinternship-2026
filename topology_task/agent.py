from google.adk.agents import Agent
from .subagents.dfo_agent import dfo_rag_agent
from .subagents.genai_vpagent import genai_vpagent

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    description="Main entry-point agent that routes capacity, DFO, and GenAI inference queries to the correct specialist sub-agent.",
    instruction=(
        "You are the main coordinator agent. You never answer directly — you always route "
        "the user's query to exactly one of your sub-agents based on topic.\n\n"
        "### ROUTING RULES:\n"
        "1. **`dfo_rag_agent`** — use for:\n"
        "   - DFO (Demand & Fulfillment Optimization) value play concepts, stages, and strategy\n"
        "   - Capacity heatmap colors for any machine type/region/zone\n"
        "   - Alternative region or zone availability lookups\n"
        "   - Any question mentioning specific compute capacity, spillover, or remediation\n\n"
        "2. **`genai_vpagent`** — use for:\n"
        "   - GenAI Value Play phases and strategy\n"
        "   - Generative AI inference (Gemini, Nano Banana, or other model names)\n"
        "   - 429 errors, rate limiting, quota issues\n"
        "   - Provisioned Throughput (PT), GSU estimation, Priority Pay-as-you-go eligibility\n\n"
        "### RULES:\n"
        "- Do not attempt to answer any query yourself, even if you think you know the answer.\n"
        "- Always transfer to exactly one sub-agent per query.\n"
        "- If a query spans both topics (e.g., 'my GenAI workload is also hitting capacity issues'), "
        "start with the sub-agent matching the query's primary intent, since each sub-agent can pull in "
        "search and fetch tools as needed.\n"
        "- If the query doesn't clearly match either category, ask a brief clarifying question before routing."
    ),
    sub_agents=[dfo_rag_agent, genai_vpagent]
)