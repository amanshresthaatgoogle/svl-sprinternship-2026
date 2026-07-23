import os
import re
import json
import csv

from google.adk import Agent
from google.adk.tools.tool_context import ToolContext

# Path to the local heatmap data file (Sheets API requires a service account
# key we don't have access to, so we read the CSV directly instead).
HEATMAP_CSV_PATH = os.path.join(os.path.dirname(__file__), "heatmap.csv")


def _load_heatmap_rows():
    """Reads the local heatmap CSV and returns its rows."""
    with open(HEATMAP_CSV_PATH, "r", encoding="utf-8") as f:
        return list(csv.reader(f))


def resolve_region_zone(region: str, zone: str = None):
    """Normalizes region/zone. If `region` actually contains a zone
    (e.g., 'australia-southeast1-a'), resolves region to
    'australia-southeast1' and zone to 'australia-southeast1-a'.
    """
    region = (region or "").strip().lower()
    zone = (zone or "").strip().lower() if zone else None

    def is_zone(s: str) -> bool:
        return bool(re.search(r"-[a-z]$", s))

    if is_zone(region):
        zone = zone or region
        region = region.rsplit("-", 1)[0]
    elif zone and is_zone(zone) and not region:
        region = zone.rsplit("-", 1)[0]

    return region, zone


def resolve_vm_family_machine_domain(vm_family: str, machine_domain: str = None):
    """Normalizes vm_family/machine_domain. If `vm_family` contains
    underscores or hyphens (e.g., 'c3_standard_lssd'), resolves vm_family
    to 'c3' and machine_domain to 'c3_standard_lssd'.
    """
    vm_family = (vm_family or "").strip().lower()
    machine_domain = (machine_domain or "").strip().lower() if machine_domain else None

    if "_" in vm_family or "-" in vm_family:
        machine_domain = machine_domain or vm_family
        vm_family = re.split(r"[_-]", vm_family)[0]

    return vm_family, machine_domain


def get_heatmap_data(
    tool_context: ToolContext,
    region: str,
    vm_family: str,
    zone: str = None,
    machine_domain: str = None
) -> str:
    """Retrieves the capacity heatmap color of a VM family in a specific Google Cloud region or zone.

    Args:
        tool_context: Automatically injected session state.
        region: The Google Cloud region (e.g., "australia-southeast1" or "us-central1").
        vm_family: The machine family of the VM (e.g., "c3", "h3", "n2").
        zone: Optional Google Cloud zone (e.g., "australia-southeast1-a" or "us-central1-a").
        machine_domain: Optional machine domain name.

    Returns:
        A JSON string containing the resolved color (green, yellow, red, very red) or error details.
    """
    resolved_region, resolved_zone = resolve_region_zone(region, zone)
    resolved_vm_family, resolved_machine_domain = resolve_vm_family_machine_domain(vm_family, machine_domain)

    rows = _load_heatmap_rows()

    if not rows:
        return json.dumps({"status": "error", "message": "The spreadsheet is empty."})

    header = [str(cell).strip().lower() for cell in rows[0]]
    col_indices = {
        col: header.index(col)
        for col in ("region", "zone", "vm_family", "machine_domain", "percentage_sold")
        if col in header
    }

    missing_cols = [c for c in ("region", "vm_family", "percentage_sold") if c not in col_indices]
    if missing_cols:
        return json.dumps({
            "status": "error",
            "message": f"Data is missing required columns: {missing_cols}. Header was: {header}"
        })

    def get_val(row, col_name):
        idx = col_indices.get(col_name)
        return str(row[idx]).strip().lower() if idx is not None and idx < len(row) else ""

    matched_percentages = []
    for row in rows[1:]:
        if not row:
            continue
        if get_val(row, "region") != resolved_region:
            continue
        if get_val(row, "vm_family") != resolved_vm_family:
            continue
        if resolved_zone and get_val(row, "zone") != resolved_zone:
            continue
        if resolved_machine_domain and get_val(row, "machine_domain") != resolved_machine_domain:
            continue

        pct_str = get_val(row, "percentage_sold")
        if not pct_str:
            continue

        val = float(pct_str.replace("%", "")) if "%" in pct_str else float(pct_str)
        if 0.0 < val <= 1.0:
            val *= 100.0
        matched_percentages.append(val)

    if not matched_percentages:
        params_desc = f"vm_family='{vm_family}', region='{resolved_region}'"
        if resolved_zone:
            params_desc += f", zone='{resolved_zone}'"
        if resolved_machine_domain:
            params_desc += f", machine_domain='{resolved_machine_domain}'"
        return json.dumps({
            "status": "error",
            "message": f"No availability data found matching: {params_desc}."
        })

    average_pct = sum(matched_percentages) / len(matched_percentages)

    # Less than 40 -> green, 40-70 -> yellow, 70-90 -> red, above 90 -> very red.
    if average_pct < 40:
        color = "green"
    elif average_pct < 70:
        color = "yellow"
    elif average_pct <= 90:
        color = "red"
    else:
        color = "very red"

    # CRITICAL: We do NOT return average_pct here, to prevent any leakage
    # of raw numbers/percentages back to the TAM.
    return json.dumps({
        "status": "success",
        "color": color,
        "vm_family": vm_family,
        "region": resolved_region,
        "zone": resolved_zone,
        "machine_domain": resolved_machine_domain
    })


root_agent = Agent(
    name="heatmap_agent",
    model="gemini-2.5-flash",
    description="An agent that reports capacity heatmap colors of Google Cloud VM families in specific regions and zones from a private Google Sheet.",
    instruction=(
        "You are an expert Google Cloud capacity and VM availability advisor agent. "
        "Your role is to answer Technical Account Manager (TAM) questions regarding the availability of "
        "VM families in various locations using a color heatmap.\n\n"

        "### CRITICAL COMMUNICATION RULES:\n"
        "1. ABSOLUTELY CANNOT SAY ANY NUMBER OR PERCENTAGE back to the TAM under any circumstances. "
        "Do NOT mention any statistics, averages, percentages, raw counts, core counts, or numeric values in your response. "
        "You must ONLY reply with the color associated with the availability.\n"
        "2. Your reply must specify the VM family, the region (or zone), and the availability color clearly (e.g. 'c3 in australia-southeast1 is red right now').\n"
        "3. When answering, use the exact location string requested by the TAM (e.g. if they ask for australia-southeast1-a, refer to australia-southeast1-a).\n"
        "4. If the TAM's query does not clearly specify BOTH a vm_family and a region, do NOT guess or assume "
        "either value. Ask the TAM to clarify the missing information before calling the tool.\n\n"

        "### OPERATIONAL WORKFLOW:\n"
        "1. From the TAM's query, extract the parameters:\n"
        "   - `vm_family` (required, e.g., 'c3', 'h3', 'n2')\n"
        "   - `region` (required, e.g., 'australia-southeast1')\n"
        "   - `zone` (optional, e.g., 'australia-southeast1-a')\n"
        "   - `machine_domain` (optional)\n"
        "   Note: If the TAM only gives a zone (e.g., 'australia-southeast1-a') and no separate region, pass that value as `region` anyway — the tool will automatically split it into the correct region and zone.\n"
        "2. Call the `get_heatmap_data` tool with the extracted parameters.\n"
        "3. Read the tool's response. Extract the 'color' value from the success JSON.\n"
        "4. Formulate your response containing ONLY the color, VM family, and location, maintaining a helpful, expert tone."
    ),
    tools=[get_heatmap_data],
)