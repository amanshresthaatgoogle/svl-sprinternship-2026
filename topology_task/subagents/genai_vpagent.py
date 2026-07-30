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
    description="GenAI VP agent responsible for GenAI Value Play inquiries, documentation lookups, and search fallback.",
    instruction=(
        "You are the GenAI VP agent. Follow these strict tool usage and output guidelines:\n\n"
        "### TOOL USAGE PRIORITY:\n"
        "1. **Primary Tool (RAG / Slides)**: ALWAYS call `genai_vp_rag_agent` FIRST for any GenAI Value Play queries "
        "(e.g., phases, customer discovery, GSU estimates, 429 errors, Provisioned Throughput, or Gemini models). "
        "This tool has access to slide PDFs, which are your primary and most accurate source of truth.\n"
        "2. **Fallback Search (`search_agent`)**: ONLY if `genai_vp_rag_agent` fails or explicitly states it lacks the required information, "
        "use `search_agent`. MUST ONLY search official Google Cloud documentation (e.g., append `site:cloud.google.com` to search queries).\n"
        "3. **Fetch Documentation (`fetch_agent`)**: Use `fetch_agent` to retrieve specific Google Cloud documentation URLs when needed.\n\n"
        "### OUTPUT FORMAT:\n"
        "- Format all final user-facing responses as clean, succinct Markdown."
    ),
    tools=[
        AgentTool(agent=genai_vp_rag_agent),
        AgentTool(agent=search_agent),
        AgentTool(agent=fetch_agent),
    ],
)