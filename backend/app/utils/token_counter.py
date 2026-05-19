"""
Token counting and cost estimation utilities.
"""
from typing import Dict, Optional


# Approximate token counts per model (input / output cost per million tokens)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "claude-opus-4-5": {
        "input_per_mtok":  15.0,
        "output_per_mtok": 75.0,
    },
    "claude-sonnet-4-5": {
        "input_per_mtok":  3.0,
        "output_per_mtok": 15.0,
    },
    "claude-haiku-4-5": {
        "input_per_mtok":  0.25,
        "output_per_mtok": 1.25,
    },
}


def count_tokens_approximate(text: str) -> int:
    """
    Rough token count approximation:
    ~4 characters per token on average for English/code.
    """
    return max(1, len(text) // 4)


def estimate_cost_usd(
    total_tokens: int,
    model: str,
    input_fraction: float = 0.6,
) -> float:
    """
    Estimate USD cost for a given token count.

    Args:
        total_tokens:   Total tokens used (input + output combined).
        model:          Model name string.
        input_fraction: Fraction of tokens that are input (default 0.6).

    Returns:
        Estimated USD cost as a float.
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-5"])

    input_tokens  = int(total_tokens * input_fraction)
    output_tokens = total_tokens - input_tokens

    input_cost  = (input_tokens  / 1_000_000) * pricing["input_per_mtok"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_mtok"]

    return round(input_cost + output_cost, 6)


def format_cost(usd: float) -> str:
    """Format a USD cost for display."""
    if usd < 0.001:
        return f"< $0.001"
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.3f}"


def format_tokens(n: int) -> str:
    """Format a token count for display."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)
