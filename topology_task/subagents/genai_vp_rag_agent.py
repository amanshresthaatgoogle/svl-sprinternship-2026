import os

from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from google.adk.agents import Agent

genai_rag_corpora_string = os.environ["RAG_CORPORA_STRING"]  # actually pull it from env

company_policies_retrieval = VertexAiRagRetrieval(
    name='dfo_vp',
    description='Details on DFO value play.',
    rag_corpora=[genai_rag_corpora_string],  # plain list, not a set
)

genai_vp_rag_agent = Agent(
    name='genai_vp_rag_agent',
    model='gemini-2.5-flash',
    instruction='gives details on dfo value play.',
    description='gives details on dfo value play.',
    tools=[company_policies_retrieval],
)