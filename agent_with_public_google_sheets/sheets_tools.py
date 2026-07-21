import os
import csv
import urllib.request
import urllib.parse
import io

_SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")

def read_sheet(range_name: str) -> dict:
    """Read values from a public spreadsheet without authentication.
    
    Args:
        range_name: A1 notation sheet name or range, e.g. "Sheet1" or "Sheet1!A1:D20".
                    (Note: The public CSV export will fetch the entire specified sheet tab).
    """
    try:
        # Extract the sheet name in case the agent passes a specific range (e.g., "Sheet1!A1:D20")
        sheet_name = range_name.split("!")[0]
        
        # Build the public CSV export URL
        url = (
            f"https://docs.google.com/spreadsheets/d/{_SPREADSHEET_ID}/export"
            f"?format=csv&sheet={urllib.parse.quote(sheet_name)}"
        )
        
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
            
        # Parse the CSV data into a list of rows
        reader = csv.reader(io.StringIO(content))
        values = list(reader)
        
        return {"values": values}
    except Exception as e:
        return {"error": str(e)}
