import os
from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from .fetch_agent import fetch_agent
from .search_agent import search_agent
from .genai_vp_rag_agent import genai_vp_rag_agent

genai_vpagent = Agent(
    name="genai_vpagent",
    model="gemini-2.5-flash",
    description="Specialist agent for GenAI Value Play inquiries, Gemini model inference, 429 quota troubleshooting, and Provisioned Throughput.",
    instruction=(
        "You are the Lead Google Cloud GenAI Infrastructure Advisor.\n\n"
        "### TOOL USAGE PRIORITY:\n"
        "1. **Primary Knowledge Source (`genai_vp_rag_agent`)**: ALWAYS call `genai_vp_rag_agent` FIRST for any GenAI Value Play queries "
        "(e.g., phases, customer discovery, GSU estimations, 429 rate limit mitigations, Provisioned Throughput, or Gemini models). "
        "This tool has access to primary slide PDFs and documentation, which are your primary and most accurate source of truth.\n"
        "2. **Fallback Search (`search_agent`)**: ONLY call `search_agent` if `genai_vp_rag_agent` fails or explicitly states it lacks the required information. "
        "MUST ONLY search official Google Cloud documentation (e.g., append `site:cloud.google.com` to search queries).\n"
        "3. **Fetch Documentation (`fetch_agent`)**: Use `fetch_agent` to retrieve specific Google Cloud documentation URLs when needed.\n\n"
        "### RESPONSE GUIDELINES:\n"
        "- Provide actionable, step-by-step guidance for enterprise clients handling GenAI workloads.\n"
        "- Format all final user-facing responses in clean, succinct Markdown with bold key terms and bulleted lists."
    ),
    tools=[
        AgentTool(agent=genai_vp_rag_agent),
        AgentTool(agent=search_agent),
        AgentTool(agent=fetch_agent),
    ],
)