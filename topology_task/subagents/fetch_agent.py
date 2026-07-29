import ssl
import urllib.request
import certifi
import logging
from google.adk.agents import Agent

logger = logging.getLogger(name)

def fetch_url(url: str) -> str:
    """
    url:str : Input URL

    fetches this URL and sends the value of the web page in html
    """
    context = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=context) as response:
        return response.read().decode("utf-8")

fetch_agent = Agent(
    name="fetch_agent",
    model="gemini-2.5-flash",
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
    """),
    tools=[fetch_url],
)