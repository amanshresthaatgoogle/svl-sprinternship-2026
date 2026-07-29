from google.adk.agents import Agent
from .subagents.dfo_agent import heatmap_agent
from .subagents.genai_vpagent import genai_vpagent

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    description="Main entry-point agent that delegates capacity, DFO, and GenAI queries.",
    instruction=(
        "You are the main coordinator agent.\n\n"
        "Your role is to handle user queries by delegating them appropriately:\n"
        "1. For capacity heatmap queries or questions about Google Cloud VM instance colors, delegate to `heatmap_agent`.\n"
        "2. For DFO value play queries or documentation requests, delegate to `heatmap_agent`.\n"
        "3. For questions about GenAI, generative AI tools, or related capabilities, delegate to `genai_agent`.\n"
        "4. Do not answer directly if a query falls into any of these categories; always delegate to the respective subagent."
    ),
    sub_agents=[heatmap_agent, genai_vpagent]
)