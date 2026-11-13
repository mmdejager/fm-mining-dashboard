"""AI market briefings using the Claude API.

The API key is read from .streamlit/secrets.toml (ANTHROPIC_API_KEY = "...")
or from the ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import os

import anthropic
import streamlit as st

import config

SYSTEM_PROMPT = """You write short, factual market briefings on the mining sector for a \
reader based in South Africa who follows South African, African and global mining \
companies and commodity prices.

Work only from the price data, news headlines and JSE SENS announcements in the \
user's message. Do not add facts, figures or events that are not in that material; \
if something important is unclear from a headline alone, say so briefly. Refer to \
stories by their [number] so the reader can find them. Rand moves matter: a weaker \
rand lifts rand-denominated metal prices for SA producers.

Write in plain British/South African English. Use Markdown with short sections and \
bullets. Do not give buy/sell recommendations or investment advice."""

BRIEFING_INSTRUCTIONS = """Write today's mining-sector briefing with these sections:

**Headline** - two or three sentences on what mattered most today.
**Commodities** - the main price moves (USD and ZAR where relevant) and what the news says is driving them.
**South Africa** - JSE miners and SA mining news, including notable SENS announcements.
**Rest of Africa** - key developments.
**Global** - the majors and global themes.
**Watch list** - three to five things worth following up.

Keep it under about 450 words."""

FOCUS_INSTRUCTIONS = """Summarise the stories below for the reader. Group them into themes, \
say what each theme means for mining companies or commodity prices, and flag anything \
that looks material for a specific company. Keep it under about 300 words."""


def api_key() -> str | None:
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        key = None
    return key or os.environ.get("ANTHROPIC_API_KEY")


def is_configured() -> bool:
    return bool(api_key())


@st.cache_data(ttl=60 * 60, show_spinner=False)
def _generate(prompt: str, instructions: str, key_hint: str) -> str:
    # key_hint only makes the cache key change if the key changes; never logged
    client = anthropic.Anthropic(api_key=api_key())
    response = client.beta.messages.create(
        model=config.AI_MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium"},
        # If the model declines, the API retries on a fallback model automatically
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": f"{prompt}\n\n{instructions}"}],
    )
    if response.stop_reason == "refusal":
        return "_The model declined to write this summary._"
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n_(Summary was cut off.)_"
    return text


def summarise(material: str, mode: str = "briefing") -> str:
    """mode: 'briefing' for the daily briefing, 'focus' for a set of filtered stories."""
    instructions = BRIEFING_INSTRUCTIONS if mode == "briefing" else FOCUS_INSTRUCTIONS
    key = api_key() or ""
    try:
        return _generate(material, instructions, key[-6:])
    except anthropic.AuthenticationError:
        raise RuntimeError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.PermissionDeniedError:
        raise RuntimeError("This API key doesn't have access to the model.")
    except anthropic.RateLimitError:
        raise RuntimeError("Rate limited by the Claude API. Try again in a minute.")
    except anthropic.APIConnectionError:
        raise RuntimeError("Couldn't reach the Claude API. Check your internet connection.")
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Claude API error ({e.status_code}): {e.message}")
