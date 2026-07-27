"""
Main ADK Agent entry point for agent_with_fetch_and_search.
Uses SequentialAgent to run sub-agents deterministically and output JSON.
"""

import logging
from google.adk.agents import SequentialAgent, LlmAgent, Agent
from google.adk.tools import google_search

import ssl
import certifi


logger = logging.getLogger(__name__)

# # 1. Synthesis Agent to combine sub-agent findings into strict JSON
# synthesis_agent = LlmAgent(
#     name="synthesis_agent",
#     model="gemini-2.5-flash",
#     description="Synthesizes regional findings into final JSON format.",
#     instruction=(
#         "You are the final synthesis agent.\n\n"
#         "Review the information gathered by search_agent and fetch_agent.\n"
#         "Synthesize all regional findings into the EXACT JSON format required below:\n\n"
#         "{\n"
#         '  "models": [\n'
#         "    {\n"
#         '      "model": "<model_name>",\n'
#         '      "ondemand_available_region": ["us-central1", "us-east4", "europe-west1", "asia-northeast1", "global"],\n'
#         '      "pt_available_region": ["us-central1", "us-east4", "europe-west1"],\n'
#         '      "prioritypaygo_available_region": ["us-central1", "us-west1", "global"],\n'
#         '      "flex_available_region": ["us-central1", "europe-west4"],\n'
#         '      "batch_available_region": ["us-central1", "us-east4"]\n'
#         "    }\n"
#         "  ]\n"
#         "}\n\n"
#         "Rules:\n"
#         "1. Populate each list with the actual region strings retrieved from the search and fetch agents.\n"
#         "2. Output ONLY the raw JSON object matching the target structure."
#     ),
# )

# 2. Root Sequential Agent (Forces search_agent -> fetch_agent -> synthesis_agent)
# root_agent = SequentialAgent(
#     name="root_agent",
#     sub_agents=[search_agent, fetch_agent, synthesis_agent],
#     description="Runs search_agent, fetch_agent, and synthesis_agent sequentially to produce JSON output.",
# )

# __all__ = ["root_agent"]

import urllib

def fetch_url(url:str) ->str:
    """
    url:str : Input URL

    fetches this URL and sends the value of the web page in html
    """
    # context = ssl._create_unverified_context()
    context = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers ={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, context = context) as response:
        return response.read().decode("utf-8")

fetch_agent = Agent(
    name="fetch_agent",
    model="gemini-3.5-flash",
    description="agent to get contents from URL",
    instruction=("""
    
    You have access to the following URLs, depending on whether the user asks for compute classes or flex migs or bulk insert api, fetch the correct url

    For GKE, use:
    https://docs.cloud.google.com/kubernetes-engine/docs/concepts/about-compute-classes

    For MIGs, use:
    https://docs.cloud.google.com/compute/docs/instance-groups/about-instance-flexibility
    
    For Instances, use BulkInsert:
    https://docs.cloud.google.com/compute/docs/instances/multiple/about-bulk-creation
    
    For any other request, deny the request

    """
    ),
    tools = [fetch_url]
    # tools = [google_search]

)