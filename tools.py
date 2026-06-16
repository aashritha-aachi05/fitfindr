"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# Words that carry no relevance signal — stripped before scoring so they don't
# inflate matches. Includes filler, query phrasing, and size/price words that
# are handled by the agent's regex parser rather than keyword overlap.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "in", "of", "to", "on", "with",
    "i", "im", "i'm", "am", "is", "it", "my", "me", "you", "your",
    "looking", "look", "want", "wanting", "need", "needing", "find", "finding",
    "some", "something", "anything", "that", "this", "what", "whats", "what's",
    "out", "there", "would", "how", "style", "wear", "wearing", "get", "got",
    "under", "below", "less", "than", "max", "around", "about", "cheap",
    "size", "sized", "fit", "fits",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Pull meaningful keywords out of the free-text description.
    keywords = _keywords(description)

    scored: list[tuple[int, dict]] = []
    for listing in listings:
        # Price filter (inclusive). Skip if over the ceiling.
        if max_price is not None and listing["price"] > max_price:
            continue

        # Size filter (case-insensitive substring, so "M" matches "S/M").
        if size is not None and not _size_matches(size, listing["size"]):
            continue

        score = _score_listing(keywords, listing)
        if score > 0:
            scored.append((score, listing))

    # Highest score first; ties keep dataset order (stable sort on -score).
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in scored]


def _keywords(text: str) -> list[str]:
    """Lowercase, split on non-letters, and drop stopwords/short tokens."""
    tokens = re.findall(r"[a-z]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _size_matches(query_size: str, listing_size: str) -> bool:
    """Case-insensitive substring match (e.g. 'm' in 's/m', '8' in 'us 8')."""
    return query_size.strip().lower() in listing_size.lower()


def _score_listing(keywords: list[str], listing: dict) -> int:
    """
    Count keyword overlap against the listing's text fields, weighting the
    most distinctive fields (title, style_tags, category) higher than the
    free-text description.
    """
    weighted_text = " ".join(
        [
            listing["title"], listing["title"],          # title counts double
            " ".join(listing["style_tags"]),
            " ".join(listing["style_tags"]),              # tags count double
            listing["category"],
            listing["description"],
            " ".join(listing["colors"]),
            listing.get("brand") or "",
        ]
    ).lower()
    haystack = set(re.findall(r"[a-z]+", weighted_text))

    score = 0
    for kw in keywords:
        # Re-count occurrences so doubled fields actually boost the score.
        score += len(re.findall(rf"\b{re.escape(kw)}\b", weighted_text)) if kw in haystack else 0
    return score


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # Replace this with your implementation
    return ""


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Replace this with your implementation
    return ""
