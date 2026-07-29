from google.adk.agents import Agent
from google.adk.tools import AgentTool
import os
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from .fetch_agent import fetch_agent
from .search_agent import search_agent
#from vertexai.preview import rag
from .genai_vp_rag_agent import genai_vp_rag_agent  # 1. Import RAG agent

genai_rag_corpora_string = os.environ["RAG_CORPORA_STRING"]  # actually pull it from env

genai_vp_retrieval = VertexAiRagRetrieval(
    name='genai_vp',
    description='Details on gen ai inference.',
    rag_corpora=[genai_rag_corpora_string],  # plain list, not a set
)


genai_vpagent = Agent(
    name="genai_vpagent",
    model="gemini-2.5-flash",
    description="GenAI VP agent responsible for delegating search, URL fetching, and RAG/Value Play requests.",
    instruction=(
        "You are the GenAI VP agent. Always delegate tasks to your tools:\n"
        "1. Use search_agent tool for general web search queries.\n"
        "2. Use fetch_agent tool for fetching specific Google Cloud documentation.\n"
        "3. Use genai_vp_rag_agent tool whenever there are questions about the GenAI Value Play "
        "(e.g., phases of the value play, customer discovery, or Generative AI inference details)."
    ),
    tools=[
        AgentTool(agent=search_agent),
        AgentTool(agent=fetch_agent),
        AgentTool(agent=genai_vp_rag_agent),
    ],
)