"""
Root agent definition: an ADK agent that can read/write a Google Sheet.
Run with `adk web` or `adk run agent_doc` from the parent directory.
"""

import os
from dotenv import load_dotenv
from google.adk.agents import Agent

from .sheets_tools import read_sheet

load_dotenv()

root_agent = Agent(
    name="sheets_agent",
    model="gemini-2.5-flash",
    description="An agent that can read from and write to a specific Google Sheet.",
    instruction=(
        "You help the user inspect and update a Google Sheet. "
        "Use read_sheet to look at data before writing. "
        "Use write_sheet to overwrite a specific range, and append_row "
        "to add a new row at the end of the data. "
        "Always confirm the range/values you're about to write before "
        "calling a write tool if the user's intent is ambiguous. "
        "Report back the result of each tool call clearly."
    ),
    tools=[read_sheet],
)
