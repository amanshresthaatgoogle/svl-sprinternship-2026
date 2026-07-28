"""
pt_gsu_calculator.py

Provisioned Throughput (PT) / GSU calculator for Vertex AI Gemini models.

Built to drop straight into a Google Agent Development Kit (ADK) agent as a
pair of "tool" functions (see section 4 at the bottom), but every function
also runs standalone in Cloud Shell Editor for quick testing:

    python3 pt_gsu_calculator.py

--------------------------------------------------------------------------
WHY TWO TOOLS INSTEAD OF ONE
--------------------------------------------------------------------------
Different Gemini models label the *same concept* with different token-
category names -- e.g. "the model's answer text" is called
`output_text_token` on some models, `output_text_response_token` on
others, and `output_response_text_token` on others still. A single flat
tool with one fixed parameter per possible name is ambiguous for an LLM
agent to fill in correctly -- it can guess the wrong parameter and the
mistake fails silently (unused categories are just treated as 0).

So the agent is expected to call two tools in sequence:
  1. `get_required_token_categories(model)` -- returns the *exact* category
     keys (with plain-English descriptions and burndown rates) that this
     specific model uses.
  2. `gsu_tool(model, ..., input_tokens={...}, output_tokens={...})` -- the
     agent fills the two dicts using ONLY the keys it just received from
     step 1. `gsu_tool` validates every key it's given and raises a clear
     error (listing the valid keys) if anything doesn't match, so mistakes
     surface immediately instead of silently computing as 0.

--------------------------------------------------------------------------
THE FIVE FORMULAS
--------------------------------------------------------------------------
1) total_burndown_adjusted_input_tokens_per_query
       = sum( input_tokens[category] * burndown_rate[category] )
         over every INPUT token category the model supports

2) total_burndown_adjusted_output_tokens_per_query
       = sum( output_tokens[category] * burndown_rate[category] )
         over every OUTPUT token category the model supports

3) tokens_per_query
       = total_burndown_adjusted_input_tokens_per_query
       + total_burndown_adjusted_output_tokens_per_query

4) total_throughput_per_second
       = tokens_per_query * queries_per_second

5) GSU
       = total_throughput_per_second / per_second_throughput_per_gsu

   Cost for a given commitment = GSU * price_per_gsu(commitment, region)
   (price is quoted per Week for the 1-week commit, and per Month for the
   1-month / 3-month / 1-year commits — see PRICING below)
--------------------------------------------------------------------------
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Union
import json
import math


# ==========================================================================
# 1. MODEL CATALOG
#    per_second_throughput_per_gsu  and  burndown_rates  taken directly from
#    the "Model / Region / Price - Calculating PT" reference table.
#
#    Only include the token categories a model actually supports — the
#    calculator simply ignores/zeros-out categories that aren't in a
#    model's dict, so you can pass a superset of fields safely.
# ==========================================================================

MODEL_CATALOG: Dict[str, dict] = {
    "gemini-3.6-flash": {
        "per_second_throughput_per_gsu": 675,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "input_audio_token": 1,
            "input_text_caching_token": 0.1,
            "input_image_caching_token": 0.1,
            "input_video_caching_token": 0.1,
            "input_audio_caching_token": 0.1,
            "output_text_response_token": 5,
        },
    },
    "gemini-3.5-flash-lite": {
        "per_second_throughput_per_gsu": 3360,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "input_audio_token": 1,
            "input_text_caching_token": 0.1,
            "input_image_caching_token": 0.1,
            "input_video_caching_token": 0.1,
            "input_audio_caching_token": 0.1,
            "output_text_response_token": 9,
        },
    },
    "gemini-3.1-flash-lite-image": {  # Nano Banana 2 Lite
        "per_second_throughput_per_gsu": 4030,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "output_response_text_token": 6,
            "output_reasoning_text_token": 6,
            "output_image_token": 120,
        },
    },
    "gemini-3-pro-image": {
        "per_second_throughput_per_gsu": 500,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "output_response_text_token": 6,
            "output_reasoning_text_token": 6,
            "output_image_token": 60,
        },
    },
    "gemini-3.1-flash-image": {
        "per_second_throughput_per_gsu": 2015,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "output_response_text_token": 6,
            "output_reasoning_text_token": 6,
            "output_image_token": 120,
        },
    },
    "gemini-3.5-flash": {
        "per_second_throughput_per_gsu": 675,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "input_audio_token": 1,
            "input_text_caching_token": 0.1,
            "input_image_caching_token": 0.1,
            "input_video_caching_token": 0.1,
            "input_audio_caching_token": 0.1,
            "output_text_token": 6,
        },
    },
    "gemini-3.1-flash-lite": {
        "per_second_throughput_per_gsu": 4030,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "input_audio_token": 2,
            "input_text_caching_token": 0.1,
            "input_image_caching_token": 0.1,
            "input_video_caching_token": 0.1,
            "input_audio_caching_token": 0.2,
            "output_response_text_token": 6,
            "output_reasoning_text_token": 6,
        },
    },
    "gemini-3-flash-preview": {
        "per_second_throughput_per_gsu": 2015,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "input_audio_token": 2,
            "input_text_caching_token": 0.1,
            "input_image_caching_token": 0.1,
            "input_video_caching_token": 0.1,
            "input_audio_caching_token": 0.2,
            "output_response_text_token": 6,
            "output_reasoning_text_token": 6,
        },
    },
    "gemini-3-pro-image-preview": {
        "per_second_throughput_per_gsu": 500,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "output_text_token": 6,
            "output_thinking_token": 6,
            "output_image_token": 60,
        },
    },
    "gemini-2.5-pro": {
        # Tiered by context length: <=200k vs >200k tokens.
        "per_second_throughput_per_gsu": 650,
        "burndown_rates": {
            "input_text_token_le200k": 1,
            "input_image_token_le200k": 1,
            "input_video_token_le200k": 1,
            "input_audio_token_le200k": 1,
            "output_response_text_token_le200k": 8,
            "output_reasoning_text_token_le200k": 8,
            "input_text_token_gt200k": 2,
            "input_image_token_gt200k": 2,
            "input_video_token_gt200k": 2,
            "input_audio_token_gt200k": 2,
            "output_response_text_token_gt200k": 12,
            "output_reasoning_text_token_gt200k": 12,
        },
    },
    "gemini-2.5-flash-image": {
        "per_second_throughput_per_gsu": 2690,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "output_text_token": 9,
            "output_image_token": 100,
        },
    },
    "gemini-2.5-flash": {
        "per_second_throughput_per_gsu": 2690,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "input_audio_token": 4,
            "output_response_text_token": 9,
            "output_reasoning_text_token": 9,
        },
    },
    "gemini-2.5-flash-lite": {
        "per_second_throughput_per_gsu": 8070,
        "burndown_rates": {
            "input_text_token": 1,
            "input_image_token": 1,
            "input_video_token": 1,
            "input_audio_token": 3,
            "output_response_text_token": 4,
            "output_reasoning_text_token": 4,
        },
    },
    "gemini-live-2.5-flash-native-audio": {
        "per_second_throughput_per_gsu": 1620,
        "burndown_rates": {
            "input_text_token": 1,
            "input_audio_token": 6,
            "input_video_token": 6,
            "input_image_token": 6,
            "input_session_memory_token": 1,
            "output_text_token": 4,
            "output_audio_token": 24,
        },
    },
}


# ==========================================================================
# 2. PRICING TABLE
#    Price is per GSU. Weekly commit is priced per Week; the 1-month,
#    3-month, and 1-year commits are all priced per Month (the 3-month and
#    1-year figures are simply a lower *monthly* rate in exchange for a
#    longer commitment — you still pay every month).
# ==========================================================================

PRICING = {
    "1_week": {"unit": "week", "global": 1200, "non_global": 1320},
    "1_month": {"unit": "month", "global": 2700, "non_global": 2970},
    "3_month": {"unit": "month", "global": 2400, "non_global": 2640},
    "1_year": {"unit": "month", "global": 2000, "non_global": 2200},
}


# ==========================================================================
# 2b. CATEGORY DESCRIPTIONS
#     Plain-English meaning of every raw token-category key that appears
#     anywhere in MODEL_CATALOG. Different models use different key names
#     for the same underlying concept (see module docstring) -- this dict
#     is what lets `get_required_token_categories` explain, in words, what
#     each of a specific model's keys actually represents.
# ==========================================================================

CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "input_text_token": "Text tokens in the prompt/input.",
    "input_image_token": "Image tokens in the prompt/input.",
    "input_video_token": "Video tokens in the prompt/input.",
    "input_audio_token": "Audio tokens in the prompt/input.",
    "input_text_caching_token": "Cached (previously seen) text tokens in the input.",
    "input_image_caching_token": "Cached (previously seen) image tokens in the input.",
    "input_video_caching_token": "Cached (previously seen) video tokens in the input.",
    "input_audio_caching_token": "Cached (previously seen) audio tokens in the input.",
    "input_session_memory_token": "Tokens carried over as session/live-conversation memory.",
    "input_text_token_le200k": "Input text tokens, counted while total context is <= 200k tokens.",
    "input_image_token_le200k": "Input image tokens, counted while total context is <= 200k tokens.",
    "input_video_token_le200k": "Input video tokens, counted while total context is <= 200k tokens.",
    "input_audio_token_le200k": "Input audio tokens, counted while total context is <= 200k tokens.",
    "input_text_token_gt200k": "Input text tokens, counted once total context exceeds 200k tokens.",
    "input_image_token_gt200k": "Input image tokens, counted once total context exceeds 200k tokens.",
    "input_video_token_gt200k": "Input video tokens, counted once total context exceeds 200k tokens.",
    "input_audio_token_gt200k": "Input audio tokens, counted once total context exceeds 200k tokens.",
    "output_text_token": "The model's output/answer text tokens.",
    "output_text_response_token": "The model's output/answer text tokens.",
    "output_response_text_token": "The model's output/answer text tokens.",
    "output_reasoning_text_token": "The model's internal reasoning/thinking tokens (not shown as the answer).",
    "output_thinking_token": "The model's internal reasoning/thinking tokens (not shown as the answer).",
    "output_image_token": "Image tokens the model generates as output.",
    "output_audio_token": "Audio tokens the model generates as output.",
    "output_response_text_token_le200k": "Output answer-text tokens, counted while total context is <= 200k tokens.",
    "output_reasoning_text_token_le200k": "Output reasoning tokens, counted while total context is <= 200k tokens.",
    "output_response_text_token_gt200k": "Output answer-text tokens, counted once total context exceeds 200k tokens.",
    "output_reasoning_text_token_gt200k": "Output reasoning tokens, counted once total context exceeds 200k tokens.",
}


# ==========================================================================
# 3. CORE CALCULATIONS
# ==========================================================================

@dataclass
class PTResult:
    model: str
    total_burndown_adjusted_input_tokens_per_query: float
    total_burndown_adjusted_output_tokens_per_query: float
    tokens_per_query: float
    queries_per_second: float
    total_throughput_per_second: float
    per_second_throughput_per_gsu: float
    gsu_exact: float
    gsu_billed: int  # rounded up -- you can only buy whole GSUs
    region: str
    costs: Dict[str, float] = field(default_factory=dict)  # commitment -> cost per billing unit


def _weighted_sum(token_counts: Dict[str, float], burndown_rates: Dict[str, float]) -> float:
    """Formula 1 & 2: multiply each supplied token count by its model-specific
    burndown rate and sum the results. Categories not defined for the model
    are ignored; categories not supplied by the caller default to 0."""
    total = 0.0
    for category, rate in burndown_rates.items():
        count = token_counts.get(category, 0) or 0
        total += count * rate
    return total


def calculate_pt(
    model: str,
    input_tokens: Dict[str, float],
    output_tokens: Dict[str, float],
    queries_per_second: float,
    region: str = "global",  # "global" or "non_global"
    gsu_purchase_increment: int | None = None,
) -> PTResult:
    """
    Run all five formulas end to end for one model / workload / region.

    input_tokens / output_tokens: dicts keyed by the burndown-rate category
        names in MODEL_CATALOG[model]["burndown_rates"], e.g.
        {"input_text_token": 1500, "input_image_token": 3}
        Any category the model doesn't use, or that you don't supply,
        is simply treated as 0.
    queries_per_second: expected sustained QPS for the workload.
    region: "global" or "non_global" -- selects the pricing column.
    gsu_purchase_increment: optional override; if the model's minimum GSU
        purchase increment differs from 1, GSUs are rounded up to the
        nearest multiple of this value (defaults to the catalog's known
        minimum purchase increment when available, else 1).
    """
    if model not in MODEL_CATALOG:
        raise ValueError(
            f"Unknown model '{model}'. Available models: {sorted(MODEL_CATALOG)}"
        )
    if region not in ("global", "non_global"):
        raise ValueError("region must be 'global' or 'non_global'")

    spec = MODEL_CATALOG[model]
    burndown_rates = spec["burndown_rates"]
    per_second_throughput_per_gsu = spec["per_second_throughput_per_gsu"]

    # Split the catalog's burndown rates into input-side and output-side
    # so formulas 1 and 2 only ever touch their own categories.
    input_rates = {k: v for k, v in burndown_rates.items() if k.startswith("input_")}
    output_rates = {k: v for k, v in burndown_rates.items() if k.startswith("output_")}

    # ---- Formula 1 ----
    total_burndown_adjusted_input_tokens_per_query = _weighted_sum(input_tokens, input_rates)

    # ---- Formula 2 ----
    total_burndown_adjusted_output_tokens_per_query = _weighted_sum(output_tokens, output_rates)

    # ---- Formula 3 ----
    tokens_per_query = (
        total_burndown_adjusted_input_tokens_per_query
        + total_burndown_adjusted_output_tokens_per_query
    )

    # ---- Formula 4 ----
    total_throughput_per_second = tokens_per_query * queries_per_second

    # ---- Formula 5 ----
    gsu_exact = total_throughput_per_second / per_second_throughput_per_gsu

    increment = gsu_purchase_increment or 1
    gsu_billed = math.ceil(gsu_exact / increment) * increment
    gsu_billed = max(gsu_billed, increment)  # never bill less than 1 increment

    # ---- Cost per commitment tier ----
    costs = {}
    for commitment, terms in PRICING.items():
        price_per_gsu = terms["global"] if region == "global" else terms["non_global"]
        costs[commitment] = {
            "price_per_gsu_per_" + terms["unit"]: price_per_gsu,
            "cost_per_" + terms["unit"]: round(price_per_gsu * gsu_billed, 2),
        }

    return PTResult(
        model=model,
        total_burndown_adjusted_input_tokens_per_query=total_burndown_adjusted_input_tokens_per_query,
        total_burndown_adjusted_output_tokens_per_query=total_burndown_adjusted_output_tokens_per_query,
        tokens_per_query=tokens_per_query,
        queries_per_second=queries_per_second,
        total_throughput_per_second=total_throughput_per_second,
        per_second_throughput_per_gsu=per_second_throughput_per_gsu,
        gsu_exact=gsu_exact,
        gsu_billed=gsu_billed,
        region=region,
        costs=costs,
    )


def format_result(result: PTResult) -> str:
    lines = [
        f"Model: {result.model}",
        f"Region: {result.region}",
        f"Burndown-adjusted input tokens/query:  {result.total_burndown_adjusted_input_tokens_per_query:,.2f}",
        f"Burndown-adjusted output tokens/query: {result.total_burndown_adjusted_output_tokens_per_query:,.2f}",
        f"Tokens per query:                      {result.tokens_per_query:,.2f}",
        f"Queries per second:                    {result.queries_per_second:,.4f}",
        f"Total throughput per second:           {result.total_throughput_per_second:,.2f}",
        f"Per-second throughput per GSU:          {result.per_second_throughput_per_gsu:,}",
        f"GSU needed (exact):                    {result.gsu_exact:,.4f}",
        f"GSU needed (billed, rounded up):        {result.gsu_billed}",
        "",
        "Cost by commitment tier:",
    ]
    for commitment, detail in result.costs.items():
        for k, v in detail.items():
            if k.startswith("cost_per_"):
                unit = k.replace("cost_per_", "")
                lines.append(f"  {commitment:>8}: ${v:,.2f} / {unit}")
    return "\n".join(lines)


# ==========================================================================
# 4. ADK TOOL WRAPPERS  (two tools, called in sequence)
#    Drop both functions straight into an ADK agent's `tools=[...]` list.
#    ADK builds each tool's schema from its type hints + docstring, so keep
#    them accurate. Both return plain dicts (JSON-serializable).
# ==========================================================================

def list_models() -> dict:
    """List every Gemini model id supported by the PT/GSU calculator.

    Call this first if you don't already know the exact model id the user
    means (e.g. they said "2.5 flash" instead of "gemini-2.5-flash").

    Returns:
        {"models": [list of valid model id strings]}
    """
    return {"models": sorted(MODEL_CATALOG.keys())}


def get_required_token_categories(model: str) -> dict:
    """Return the exact input/output token-category keys a given Gemini
    model uses for Provisioned Throughput billing, each with a plain-
    English description and its burndown rate.

    ALWAYS call this before calling `gsu_tool` for a given model. Different
    models name the same concept differently (e.g. "the model's answer
    text" may be `output_text_token`, `output_text_response_token`, or
    `output_response_text_token` depending on the model) -- this tool tells
    you precisely which key names are valid for THIS model, so you can
    build the `input_tokens` / `output_tokens` dicts for `gsu_tool`
    correctly instead of guessing.

    Args:
        model: Gemini model id, e.g. "gemini-2.5-flash". Call `list_models`
            first if you're not sure of the exact id.

    Returns:
        {
          "model": str,
          "per_second_throughput_per_gsu": number,
          "input_categories": [
              {"key": str, "description": str, "burndown_rate": number}, ...
          ],
          "output_categories": [
              {"key": str, "description": str, "burndown_rate": number}, ...
          ],
        }
        Use the "key" fields verbatim as dict keys when calling `gsu_tool`.
    """
    if model not in MODEL_CATALOG:
        raise ValueError(
            f"Unknown model '{model}'. Call list_models() for valid ids. "
            f"Available models: {sorted(MODEL_CATALOG)}"
        )

    spec = MODEL_CATALOG[model]
    burndown_rates = spec["burndown_rates"]

    input_categories = [
        {
            "key": key,
            "description": CATEGORY_DESCRIPTIONS.get(key, ""),
            "burndown_rate": rate,
        }
        for key, rate in burndown_rates.items()
        if key.startswith("input_")
    ]
    output_categories = [
        {
            "key": key,
            "description": CATEGORY_DESCRIPTIONS.get(key, ""),
            "burndown_rate": rate,
        }
        for key, rate in burndown_rates.items()
        if key.startswith("output_")
    ]

    return {
        "model": model,
        "per_second_throughput_per_gsu": spec["per_second_throughput_per_gsu"],
        "input_categories": input_categories,
        "output_categories": output_categories,
    }


def _coerce_token_dict(value: Union[Dict[str, float], str, None], arg_name: str) -> Dict[str, float]:
    """Accept either a real dict (normal case) or a JSON-object string
    (fallback case).

    Some ADK / automatic-function-calling schema builders don't reliably
    generate a correct schema for `Dict[str, float]` parameters and instead
    have the model pass the argument as a JSON-encoded string. This helper
    makes `gsu_tool` tolerant of both so you don't have to find that out at
    call time in production -- if a string comes in, it's parsed as JSON;
    if it's already a dict, it's used as-is.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"'{arg_name}' was passed as a string but isn't valid JSON: {e}. "
                f"Expected either a JSON object string like "
                f'\'{{"input_text_token": 1500}}\' or an actual dict.'
            ) from e
        if not isinstance(parsed, dict):
            raise ValueError(
                f"'{arg_name}' JSON string must decode to an object/dict, "
                f"got {type(parsed).__name__} instead."
            )
        return parsed
    raise ValueError(
        f"'{arg_name}' must be a dict or a JSON object string, "
        f"got {type(value).__name__} instead."
    )


def gsu_tool(
    model: str,
    queries_per_second: float,
    region: str,
    input_tokens: Union[Dict[str, float], str],
    output_tokens: Union[Dict[str, float], str],
) -> dict:
    """Calculate the number of GSUs and Provisioned Throughput cost needed
    for a Vertex AI Gemini workload.

    REQUIRES calling `get_required_token_categories(model)` first and using
    ONLY the exact "key" values it returns as keys in `input_tokens` /
    `output_tokens`. Any key that isn't valid for the chosen model raises a
    ValueError listing the valid keys, rather than silently being ignored.

    Args:
        model: Gemini model id, e.g. "gemini-2.5-flash".
        queries_per_second: Expected sustained queries per second.
        region: "global" or "non_global".
        input_tokens: dict mapping input token-category keys (from
            `get_required_token_categories`) to raw token counts per query.
            If your agent framework can't pass a nested dict argument, a
            JSON object string (e.g. '{"input_text_token": 1500}') is also
            accepted and will be parsed automatically.
        output_tokens: dict mapping output token-category keys (from
            `get_required_token_categories`) to raw token counts per query.
            Same JSON-string fallback as `input_tokens` applies.

    Returns:
        A dict with tokens_per_query, total_throughput_per_second,
        gsu_exact, gsu_billed, and cost per commitment tier (1_week,
        1_month, 3_month, 1_year) for the requested region.
    """
    input_tokens = _coerce_token_dict(input_tokens, "input_tokens")
    output_tokens = _coerce_token_dict(output_tokens, "output_tokens")

    if model not in MODEL_CATALOG:
        raise ValueError(
            f"Unknown model '{model}'. Call list_models() for valid ids. "
            f"Available models: {sorted(MODEL_CATALOG)}"
        )

    burndown_rates = MODEL_CATALOG[model]["burndown_rates"]
    valid_input_keys = {k for k in burndown_rates if k.startswith("input_")}
    valid_output_keys = {k for k in burndown_rates if k.startswith("output_")}

    bad_input_keys = set(input_tokens) - valid_input_keys
    bad_output_keys = set(output_tokens) - valid_output_keys
    if bad_input_keys or bad_output_keys:
        raise ValueError(
            "Invalid token category key(s) for model "
            f"'{model}': input={sorted(bad_input_keys)}, "
            f"output={sorted(bad_output_keys)}. "
            f"Call get_required_token_categories('{model}') to get the "
            f"exact valid keys. Valid input keys: {sorted(valid_input_keys)}. "
            f"Valid output keys: {sorted(valid_output_keys)}."
        )

    result = calculate_pt(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        queries_per_second=queries_per_second,
        region=region,
    )

    return {
        "model": result.model,
        "region": result.region,
        "total_burndown_adjusted_input_tokens_per_query": result.total_burndown_adjusted_input_tokens_per_query,
        "total_burndown_adjusted_output_tokens_per_query": result.total_burndown_adjusted_output_tokens_per_query,
        "tokens_per_query": result.tokens_per_query,
        "total_throughput_per_second": result.total_throughput_per_second,
        "per_second_throughput_per_gsu": result.per_second_throughput_per_gsu,
        "gsu_exact": round(result.gsu_exact, 4),
        "gsu_billed": result.gsu_billed,
        "costs": result.costs,
    }


# ==========================================================================
# 5. EXAMPLE / QUICK TEST
#    Run this file directly in Cloud Shell Editor to sanity-check the math.
# ==========================================================================

if __name__ == "__main__":
    # Direct call to calculate_pt -- fine for scripting/Cloud Shell.
    example = calculate_pt(
        model="gemini-2.5-flash",
        input_tokens={"input_text_token": 1500},
        output_tokens={
            "output_response_text_token": 300,
            "output_reasoning_text_token": 50,
        },
        queries_per_second=2.5,
        region="global",
    )
    print(format_result(example))

    print("\n--- Two-step agent-tool flow ---\n")

    # Step 1: agent discovers the correct keys for this model.
    categories = get_required_token_categories("gemini-2.5-flash")
    print("Input categories:", [c["key"] for c in categories["input_categories"]])
    print("Output categories:", [c["key"] for c in categories["output_categories"]])

    # Step 2: agent calls gsu_tool using only those keys.
    tool_result = gsu_tool(
        model="gemini-2.5-flash",
        queries_per_second=2.5,
        region="global",
        input_tokens={"input_text_token": 1500},
        output_tokens={
            "output_response_text_token": 300,
            "output_reasoning_text_token": 50,
        },
    )
    print("\ngsu_tool result:", tool_result)

    # Example of the validation catching a wrong/guessed key name:
    try:
        gsu_tool(
            model="gemini-2.5-flash",
            queries_per_second=2.5,
            region="global",
            input_tokens={"input_text_token": 1500},
            output_tokens={"output_text_token": 300},  # wrong key for this model
        )
    except ValueError as e:
        print("\nExpected validation error for a mismatched key:\n", e)

    # Example of the JSON-string fallback (in case an agent framework
    # can't pass nested dict arguments and sends JSON text instead):
    tool_result_from_json = gsu_tool(
        model="gemini-2.5-flash",
        queries_per_second=2.5,
        region="global",
        input_tokens='{"input_text_token": 1500}',
        output_tokens='{"output_response_text_token": 300, "output_reasoning_text_token": 50}',
    )
    print("\ngsu_tool result (via JSON-string args):", tool_result_from_json)
