import datetime
import time
import os
from typing import Any
from pydantic import BaseModel, Field

# --- Robust Zero-Dependency Environment Variable Loader ---
def _load_env_manually():
    import os
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val_str = val.strip().strip("'\"")
                    os.environ[key.strip()] = val_str

_load_env_manually()

from google.adk import Agent, Context, Event, Workflow
from google.adk.tools.tool_context import ToolContext
from google.adk.runners import InMemoryRunner
from google.genai import types

# --- Configuration & Placeholders ---
# Google Sheet URL for grounding
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1479hgGqT2Z3E4M-8BvUKj6OOXJMed7P5RcTFsUDiVhE/edit?gid=786787230#gid=786787230" 

# --- Input/Output Schemas ---
class RootAgentInput(BaseModel):
    model: str = Field(
        default="gemini-2.5-flash",
        description="The Google Cloud model name (e.g., gemini-2.5-flash, gemini-3.5-flash, gemini-3.1-pro-preview)"
    )
    region: str = Field(
        default="us-central1",
        description="The Google Cloud region (e.g., us-central1)"
    )
    question: str = Field(
        default="What is the difference between Gemini 3.5 Flash and Gemini 2.5 Flash on-demand pricing?",
        description="The question about Google Cloud payment models or pricing"
    )

# --- Tools ---
def pull_payment_sheet_info(tool_context: ToolContext) -> str:
    """Pulls information regarding payment models of Google Cloud (on demand, pt, priority, flex, batch)
    from the Google Sheet. Automatically records the current time as the latestcheck timestamp.

    Args:
        tool_context: The automatically injected ToolContext containing session state.

    Returns:
        A string containing the payment model information retrieved from the sheet.
    """
    import urllib.request
    import urllib.error
    import re
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tool_context.state['latestcheck'] = now_str
    
    # Check if the Google Sheet URL is set or blank
    if not GOOGLE_SHEET_URL:
        # Fallback to simulated payment model data when sheet URL is blank
        return f"""
        [Sheet Source: SIMULATED FALLBACK (Google Sheet URL is blank)]
        Latest Check Time: {now_str}
        
        Google Cloud Payment Models:
        - On Demand: Standard pay-as-you-go pricing with no upfront commitment. Fully flexible and scale-on-demand.
        - PT (Provisioned Throughput): Reserved capacity offering predictable latency and throughput, highly cost-effective for stable workloads.
        - Priority: High-availability execution with guaranteed resources for urgent tasks.
        - Flex: Flexible-commitment contracts offering discounted pricing with short-term commitments.
        - Batch: Highly discounted pricing for batch processing of background and interruptible jobs.
        """
        
    try:
        # Parse the spreadsheet ID and gid to build the CSV export URL
        sheet_id_match = re.search(r"/d/([a-zA-Z0-9-_]+)", GOOGLE_SHEET_URL)
        gid_match = re.search(r"gid=(\d+)", GOOGLE_SHEET_URL)
        
        if sheet_id_match:
            sheet_id = sheet_id_match.group(1)
            gid = gid_match.group(1) if gid_match else "0"
            export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
            
            # Fetch the CSV using urllib.request (zero external dependencies!)
            req = urllib.request.Request(
                export_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                csv_data = response.read().decode('utf-8')
                
            return f"""
            [Sheet Source: Google Sheet successfully retrieved via CSV Export]
            Latest Check Time: {now_str}
            Spreadsheet Source: {GOOGLE_SHEET_URL}
            
            --- CSV DATA ---
            {csv_data}
            """
        else:
            raise ValueError("Could not extract Sheet ID from GOOGLE_SHEET_URL")
            
    except Exception as e:
        # Clean robust fallback to simulated data if fetch fails
        return f"""
        [Sheet Source: SIMULATED FALLBACK (Fetch failed: {str(e)})]
        Latest Check Time: {now_str}
        
        Google Cloud Payment Models:
        - On Demand: Standard pay-as-you-go pricing with no upfront commitment. Fully flexible and scale-on-demand.
        - PT (Provisioned Throughput): Reserved capacity offering predictable latency and throughput, highly cost-effective for stable workloads.
        - Priority: High-availability execution with guaranteed resources for urgent tasks.
        - Flex: Flexible-commitment contracts offering discounted pricing with short-term commitments.
        - Batch: Highly discounted pricing for batch processing of background and interruptible jobs.
        """

# --- Find Info LLM Agent ---
find_info_agent = Agent(
    name="find_info",
    model="gemini-2.5-flash",
    instruction="""You are an expert Google Cloud payment models and pricing information retrieval agent.
Your instructions are as follows:
- You have been configured with model: {model} and region: {region}.
- First, you MUST call the `pull_payment_sheet_info` tool to fetch the actual sheet data and automatically record the `latestcheck` timestamp in state.
- After retrieving the sheet data, read the `latestcheck` timestamp from state (which is {latestcheck?}).
- Answer the user's question accurately using the fetched Google Sheet data.
- In your final response, make sure to:
  1. Explicitly mention your configured model ({model}) and region ({region}).
  2. Answer their question fully based on the Google Sheet content.
  3. Highlight the exact date and time the data was last checked (using the {latestcheck?} timestamp).
""",
    tools=[pull_payment_sheet_info],
    description="Retrieves information about Google Cloud payment models and pricing from the Google Sheet and answers questions.",
)

# --- Workflow Helper Functions ---
def start_node(node_input: Any) -> Event:
    """Processes the starting input for the root agent.
    Supports RootAgentInput (Pydantic), raw dict, or raw strings, extracting
    and setting state for model, region, and question accordingly.
    """
    model_val = "gemini-2.5-flash"
    region_val = "us-central1"
    question_val = ""
    
    if isinstance(node_input, RootAgentInput):
        model_val = node_input.model
        region_val = node_input.region
        question_val = node_input.question
    elif isinstance(node_input, dict):
        model_val = node_input.get("model", model_val)
        region_val = node_input.get("region", region_val)
        question_val = node_input.get("question", "")
    elif isinstance(node_input, str):
        import json
        try:
            data = json.loads(node_input)
            if isinstance(data, dict):
                model_val = data.get("model", model_val)
                region_val = data.get("region", region_val)
                question_val = data.get("question", node_input)
            else:
                question_val = node_input
        except Exception:
            question_val = node_input
    else:
        question_val = str(node_input)
        
    return Event(
        output=question_val,
        state={
            "model": model_val,
            "region": region_val,
            "question": question_val
        }
    )

# --- Root Agent Workflow ---
def create_root_agent(default_model: str = "gemini-2.5-flash", default_region: str = "us-central1") -> Workflow:
    """Creates a root agent workflow configured with a default model and region."""
    
    def bound_start_node(node_input: Any) -> Event:
        # Extract starting values, falling back to workflow defaults if not specified
        event = start_node(node_input)
        state_delta = event.actions.state_delta
        if "model" not in state_delta or not state_delta["model"]:
            state_delta["model"] = default_model
        if "region" not in state_delta or not state_delta["region"]:
            state_delta["region"] = default_region
        return event

    return Workflow(
        name="root_agent",
        edges=[
            ('START', bound_start_node),
            (bound_start_node, find_info_agent),
        ]
    )

# Standard root_agent instance discovered by ADK CLI and Web UI
root_agent = create_root_agent("gemini-2.5-flash", "us-central1")

if __name__ == '__main__':
    import asyncio
    
    async def run_test():
        print("="*60)
        print("Google Cloud Payment Model Info Retrieval Agent (ADK)")
        print("="*60)
        
        test_input = RootAgentInput(
            model="gemini-3.5-flash",
            region="us-central1",
            question="What is the standard on-demand price for Gemini 3.5 Flash input tokens and output tokens?"
        )
        
        print(f"Configured Model: {test_input.model}")
        print(f"Configured Region: {test_input.region}")
        print(f"Question: {test_input.question}")
        print("-" * 60)
        print("Starting Execution...")
        
        start_time = time.time()
        
        # Create runner
        runner = InMemoryRunner(
            app_name="gsheet_agent_test",
            agent=root_agent,
        )
        
        # Create session
        session = await runner.session_service.create_session(
            app_name="gsheet_agent_test",
            user_id="user_test_1"
        )
        
        msg = types.Content(
            role="user",
            parts=[types.Part.from_text(text=test_input.model_dump_json())]
        )
        
        print("\n--- Execution Steps ---")
        async for event in runner.run_async(
            user_id="user_test_1",
            session_id=session.id,
            new_message=msg,
        ):
            # Log any event content
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"[{event.author or 'System'}] {part.text.strip()}")
            
            # If the event represents tool execution
            if event.get_function_calls():
                for fc in event.get_function_calls():
                    print(f"\n[Tool Call] Invoking {fc.name} with args: {fc.args}\n")
                    
        end_time = time.time()
        elapsed = end_time - start_time
        
        print("-" * 60)
        print(f"Execution Completed in {elapsed:.3f} seconds.")
        print("="*60)

    asyncio.run(run_test())
