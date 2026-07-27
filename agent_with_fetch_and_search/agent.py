"""
Main ADK Agent entry point for agent_with_fetch_and_search.
Uses SequentialAgent to run sub-agents deterministically and output JSON.
"""

from google.genai._gaos.resources.interactions import tool
import logging
from google.adk.agents import SequentialAgent, LlmAgent, Agent
from google.adk.tools import google_search,AgentTool


from .sub_agents.search_agent import search_agent
from .sub_agents.fetch_agent import fetch_agent

import ssl
import certifi


logger = logging.getLogger(__name__)


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

root_agent = Agent(
    name="root_agent",
    model="gemini-3.5-flash",
    description="agent to get contents from URL",
    instruction=("""

    this is a test, always send to your subagent and don't answer directly yourself
     when the user says 
    search for anything, then call the search_agent 
    Search_agent  will do a search and return the content to you
    

    when the user says find information on GKE, compute classes, flex migs or bulk insert, always call fetch_agent
    Fetch_agent has info on what to do, so send it there. 
    """
    ),

    sub_agents = [search_agent, fetch_agent],
    # tools=[
    #     AgentTool(agent=search_agent),
    #     # Your other custom Python function tools can safely sit here!
    # ]

)


# instruction=("""

#     Do not answer anything yourself, always use your subagents
#     Depending on whether the user asks to search url or not, direct them to one of your subagents
#     the sub agents you have are
#     For fetching fetch_agent

#     "You route user requests to the appropriate sub-agent:\n"
#         "1. If the query requires web searching, delegate to search_agent.\n"
#         "2. If the query asks to fetch/scrape a specific URL, delegate to fetch_agent.\n"
#         "Once the sub-agent completes its work, summarize its response directly to the user. "
#         "Do NOT delegate back and forth."
#     """
#     ),