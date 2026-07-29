"""
Main ADK Agent entry point for agent_with_fetch_and_search.
Uses SequentialAgent to run sub-agents deterministically and output JSON.
"""

import logging
from google.adk.agents import SequentialAgent, LlmAgent, Agent
from google.adk.tools import google_search


logger = logging.getLogger(__name__)


search_agent = Agent(
    name="search_agent",
    model="gemini-2.5-flash",
    description="agent to get contents from URL",
    instruction=("""
    run the query to the google_search tool and respond. don't respond without a search result
    """
    ),
    tools = [google_search]

)