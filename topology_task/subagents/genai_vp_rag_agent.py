import os

from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from google.adk.agents import Agent

genai_rag_corpora_string = os.environ["RAG_CORPORA_STRING"]  # actually pull it from env

genai_inference_retrieval = VertexAiRagRetrieval(
    name='genai_inf',
    description='Details on Generative AI inference.',
    rag_corpora=[genai_rag_corpora_string],  # plain list, not a set
)

genai_vp_rag_agent = Agent(
    name='genai_vp_rag_agent',
    model='gemini-2.5-flash',
    instruction='gives details on generative ai inference.',
    description='gives details on generative ai inference.',
    tools=[genai_inference_retrieval],
)
