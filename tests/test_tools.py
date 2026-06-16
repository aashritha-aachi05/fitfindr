"""
Failure-mode tests for the three FitFindr tools in tools.py.

Each tool documents a specific "graceful degradation" path — a case where the
input is empty/unmatched and the tool must NOT raise, but instead return a
sensible empty list or descriptive string. These tests pin down that contract:

    search_listings  → empty list when nothing matches
    suggest_outfit   → non-empty advice string when the wardrobe is empty
    create_fit_card  → descriptive error string when the outfit is empty

The LLM-backed tools call Groq, so the empty-wardrobe test stubs the client to
keep the suite offline and deterministic. create_fit_card's empty-outfit guard
returns before any network call, so it needs no stub.
"""

import tools


# ── Fixtures / helpers ──────────────────────────────────────────────────────

def _sample_item() -> dict:
    """A minimal listing dict with every field the tools read."""
    return {
        "id": "test-1",
        "title": "Vintage Levi's Denim Jacket",
        "description": "Classic washed denim trucker jacket.",
        "category": "outerwear",
        "style_tags": ["vintage", "casual"],
        "size": "M",
        "condition": "good",
        "price": 42.0,
        "colors": ["blue"],
        "brand": "Levi's",
        "platform": "depop",
    }


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, *args, **kwargs):
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeGroqClient:
    """Stand-in for the Groq client used by the LLM-backed tools."""

    def __init__(self, content):
        self.chat = _FakeChat(content)


# ── Tool 1: search_listings — empty results ─────────────────────────────────

def test_search_listings_returns_empty_list_when_nothing_matches():
    """A description with no relevant keywords must yield [] (not raise)."""
    results = tools.search_listings("zzqqxx nonexistentgibberishterm")

    assert results == []
    assert isinstance(results, list)


def test_search_listings_returns_empty_list_when_price_excludes_everything():
    """An impossibly low price ceiling filters every listing out → []."""
    results = tools.search_listings("denim jacket", max_price=0.0)

    assert results == []


# ── Tool 2: suggest_outfit — empty wardrobe ─────────────────────────────────

def test_suggest_outfit_with_empty_wardrobe_returns_general_advice(monkeypatch):
    """An empty wardrobe must still produce a non-empty styling string."""
    canned = "Pair this denim jacket with a white tee and black jeans."
    monkeypatch.setattr(
        tools, "_get_groq_client", lambda: _FakeGroqClient(canned)
    )

    result = tools.suggest_outfit(_sample_item(), {"items": []})

    assert isinstance(result, str)
    assert result.strip() != ""
    assert result == canned


def test_suggest_outfit_with_missing_items_key_does_not_raise(monkeypatch):
    """A wardrobe dict with no 'items' key is treated as empty, not an error."""
    canned = "Some general styling advice."
    monkeypatch.setattr(
        tools, "_get_groq_client", lambda: _FakeGroqClient(canned)
    )

    result = tools.suggest_outfit(_sample_item(), {})

    assert isinstance(result, str)
    assert result.strip() != ""


# ── Tool 3: create_fit_card — empty outfit string ───────────────────────────

def test_create_fit_card_with_empty_outfit_returns_error_string():
    """An empty outfit must return a descriptive string, never raise."""
    result = tools.create_fit_card("", _sample_item())

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "outfit" in result.lower()


def test_create_fit_card_with_whitespace_outfit_returns_error_string():
    """A whitespace-only outfit is treated the same as empty."""
    result = tools.create_fit_card("   \n\t  ", _sample_item())

    assert isinstance(result, str)
    assert "outfit" in result.lower()
