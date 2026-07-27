import json

from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPServerParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.genai import types

# Connects to the MCP Toolbox server
toolkit = MCPToolset(
    connection_params=StreamableHTTPServerParams(
        url="http://127.0.0.1:5000/mcp",
    ),
    tool_filter=["get_heatmap_color"],
)


def format_heatmap_response(tool, args, tool_context, tool_response):
    """
    Intercepts get_heatmap_color's raw result and builds the final
    TAM-facing reply directly, skipping the second LLM round trip.
    """
    print("CALLBACK FIRED:", tool.name)
    print("RAW TOOL RESPONSE:", tool_response)

    if tool.name != "get_heatmap_color":
        return None  # let other tools (if any) fall through to normal handling

    color = None
    try:
        if isinstance(tool_response, dict) and not tool_response.get("isError"):
            inner_text = tool_response["content"][0]["text"]
            color = json.loads(inner_text).get("color")
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        print("FAILED TO PARSE TOOL RESPONSE:", e)

    region = args.get("region", "")
    zone = args.get("zone", "")
    identifier = args.get("raw_identifier", "")
    location = zone if zone else region

    if not color or color == "no_data":
        text = f"No capacity data is available for {identifier} in {location}."
    else:
        text = f"{identifier} in {location} is {color} right now."

    tool_context.actions.skip_summarization = True
    return text


root_agent = Agent(
    name="heatmap_agent",
    model="gemini-2.5-flash",
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    ),
    description="An agent that reports capacity heatmap colors of Google Cloud VM families in specific regions and zones using a Cloud SQL MySQL database via MCP.",
    instruction=(
        "You are an expert Google Cloud capacity and VM availability advisor agent. "
        "Your role is to answer Technical Account Manager (TAM) questions regarding the availability of "
        "VM families in various locations using a color heatmap.\n\n"

        "### REQUIRED PARAMETERS:\n"
        "1. `region` and a VM identifier are ALWAYS mandatory. If BOTH are missing, or the VM identifier "
        "is missing, stop immediately and ask for clarification. Do NOT guess or default the VM identifier.\n"
        "2. `zone` is optional. Google Cloud zones always follow the pattern REGION followed by a "
        "dash and a single letter (e.g. zone 'europe-north1-a' belongs to region 'europe-north1'). "
        "If the TAM gives ONLY a zone with no separate region, derive the region yourself by "
        "stripping the zone's trailing dash-letter suffix, and pass BOTH the derived region and "
        "the given zone to `get_heatmap_color`. Do NOT ask the TAM for the region separately in "
        "this case.\n"
        "3. If the TAM gives neither a region nor a zone, stop and ask for clarification.\n\n"

        "### VM IDENTIFIER PASSING:\n"
        "1. Pass the TAM's VM identifier as `raw_identifier` to `get_heatmap_color` exactly as given — "
        "the tool itself resolves bare family names, compound identifiers, and unrelated "
        "family/domain naming (do not attempt to split, parse, or guess the identifier yourself).\n"
        "2. The ONLY transformation you make: if the TAM said the identifier as two separate words "
        "(e.g. 'n2d viperlitepod'), join them with a single underscore before passing "
        "('n2d_viperlitepod'). Otherwise pass it unmodified.\n\n"

        "### CRITICAL COMMUNICATION RULES:\n"
        "1. ABSOLUTELY CANNOT SAY ANY NUMBER OR PERCENTAGE back to the TAM under any circumstances. "
        "You must ONLY reply using the color returned directly by the `get_heatmap_color` tool.\n"
        "2. Your reply must specify the VM identifier, the location requested (region, and zone if "
        "given), and the availability color clearly (e.g. 'c3 in australia-southeast1 is red right now').\n"
        "3. If the tool returns 'no_data', state that no capacity data is available matching that "
        "identifier and location.\n"
        "4. Always reference the exact location string(s) requested by the TAM.\n\n"

        "### OPERATIONAL WORKFLOW:\n"
        "1. Extract parameters from the TAM's query: `region` (required, derive from zone if needed), "
        "VM identifier (required), `zone` (optional).\n"
        "2. If neither `region` nor `zone` was given, OR the VM identifier is missing, stop and ask "
        "for clarification.\n"
        "3. Call `get_heatmap_color` once with whichever parameters were provided.\n"
        "4. Reply to the TAM using ONLY the returned color string, VM identifier, and location."
    ),
    tools=[toolkit],
    after_tool_callback=format_heatmap_response,
)