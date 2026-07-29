from google.adk.agents import Agent
from google.adk.tools import AgentTool
import os
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from .fetch_agent import fetch_agent
from .search_agent import search_agent
from vertexai.preview import rag

genai_rag_corpora_string = os.environ["RAG_CORPORA_STRING"]  # actually pull it from env

genai_vp_retrieval = VertexAiRagRetrieval(
    name='genai_vp',
    description='Details on gen ai inference.',
    rag_corpora=[genai_rag_corpora_string],  # plain list, not a set
)


genai_vpagent = Agent(
    name="genai_vpagent",
    model="gemini-2.5-flash",
    description="GenAI VP agent responsible for delegating search and URL fetching requests.",
    instruction=(
        "You are the GenAI VP agent. Always delegate tasks to your tools:\n"
        "1. Use search_agent tool for search queries.\n"
        "2. Use fetch_agent tool for fetching documentation."
    ),
    tools=[
        AgentTool(agent=search_agent),
        AgentTool(agent=fetch_agent),
    ],
)