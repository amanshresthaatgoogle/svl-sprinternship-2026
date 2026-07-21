import os
import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")

_service = None

def _get_service():
    """Lazily build and cache the Sheets API client using ADC."""
    global _service
    if _service is not None:
        return _service

    try:
        creds, _ = google.auth.default(scopes=SCOPES)
    except Exception as e:
        raise RuntimeError(
            "No Application Default Credentials found. Run:\n"
            "  gcloud auth application-default login "
            "--scopes=openid,https://www.googleapis.com/auth/userinfo.email,"
            "https://www.googleapis.com/auth/cloud-platform,"
            "https://www.googleapis.com/auth/spreadsheets"
        ) from e

    _service = build("sheets", "v4", credentials=creds)
    return _service

def read_sheet(range_name: str) -> dict:
    """Read values from the spreadsheet using the Google Sheets API.

    Args:
        range_name: A1 notation range, e.g. "Sheet1!A1:D20" or "Sheet1".

    Returns:
        dict with "values" (list of rows) on success, or "error".
    """
    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=_SPREADSHEET_ID, range=range_name)
            .execute()
        )
        return {"values": result.get("values", [])}
    except HttpError as e:
        return {"error": str(e)}

def write_sheet(range_name: str, values: list) -> dict:
    """Overwrite cells in the given range with new values."""
    try:
        service = _get_service()
        body = {"values": values}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=_SPREADSHEET_ID,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        return {"updated_cells": result.get("updatedCells")}
    except HttpError as e:
        return {"error": str(e)}

def append_row(range_name: str, values: list) -> dict:
    """Append a new row after the last row of data in the range."""
    try:
        service = _get_service()
        body = {"values": [values]}
        result = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=_SPREADSHEET_ID,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
        return {"updates": result.get("updates")}
    except HttpError as e:
        return {"error": str(e)}
