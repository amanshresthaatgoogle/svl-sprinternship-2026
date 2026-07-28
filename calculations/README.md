# PT / GSU Sizing Agent

An ADK agent that sizes Vertex AI Provisioned Throughput: given a Gemini
model, a workload's per-query token counts, queries per second, and a
region, it returns the GSUs needed and the cost across all four
commitment tiers (1 week, 1 month, 3 month, 1 year).

## Files

- `pt_gsu_calculator.py` — the calculator logic and the three tools:
  `list_models`, `get_required_token_categories`, `gsu_tool`.
- `agent.py` — the ADK `root_agent` definition, with an instruction that
  forces the correct tool-call order (see below).
- `__init__.py` — exposes `agent` so ADK's autodiscovery can find
  `root_agent`.

## Why the agent calls two tools before calculating

Different Gemini models label the same token concept differently (e.g.
"the model's answer text" is `output_text_token` on one model and
`output_response_text_token` on another). The agent is instructed to
always call `get_required_token_categories(model)` first to get the
model's real key names before calling `gsu_tool`, rather than guessing.
`gsu_tool` also validates every key it receives and raises a clear error
if something doesn't match, so a bad guess can't silently compute as 0.

`gsu_tool`'s `input_tokens` / `output_tokens` arguments accept either a
real dict or a JSON object string, so it works regardless of how a given
agent framework/version serializes dict arguments.

## Running it in Cloud Shell Editor

```bash
pip install -r requirements.txt --break-system-packages

# From the PARENT directory of pt_gsu_agent/:
adk web
# then open the URL Cloud Shell gives you and select "pt_gsu_agent"

# or, without the UI:
adk run pt_gsu_agent
```

## Example interaction

> "I'm using gemini-2.5-flash, global region. About 1500 input text
> tokens and 300 answer tokens + 50 reasoning tokens per query, at 2.5
> queries per second. What GSUs and cost do I need?"

The agent will call `get_required_token_categories("gemini-2.5-flash")`,
map your numbers onto the correct keys (`output_response_text_token` /
`output_reasoning_text_token` for this model), call `gsu_tool`, and
report GSUs needed plus cost for all four commitment tiers.
