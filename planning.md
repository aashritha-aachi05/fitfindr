# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the 40-item mock listings dataset for pieces matching the user's
description, filters by optional size and price ceiling, scores the survivors by
keyword overlap, and returns them best-match-first. Pure Python — no LLM call.

**Input parameters:**
- `description` (str): Free-text keywords describing the desired item
  (e.g., "vintage graphic tee"). Used for relevance scoring.
- `size` (str | None): Size to filter by. Case-insensitive substring match so
  "M" matches "S/M" and "M/L". `None` skips size filtering.
- `max_price` (float | None): Inclusive price ceiling. `None` skips price filtering.

**What it returns:**
A `list[dict]` of matching listings, sorted by descending relevance score.
Each dict is a full listing: `id, title, description, category, style_tags,
size, condition, price, colors, brand, platform`. Returns `[]` when nothing
matches — never raises.

**What happens if it fails or returns nothing:**
Returns an empty list. The planning loop detects the empty list, sets a helpful
`session["error"]` ("No listings matched … try broadening your search"), and
stops before calling the LLM tools — it never passes empty input downstream.

---

### Tool 2: suggest_outfit

**What it does:**
Given the selected thrifted item and the user's wardrobe, asks the LLM (Groq) to
propose 1–2 complete outfits. Behaviour branches on whether the wardrobe has items.

**Input parameters:**
- `new_item` (dict): The listing the user is considering buying (top search result).
- `wardrobe` (dict): A wardrobe dict with an `items` list (may be empty).

**What it returns:**
A non-empty styling string. With items, it names specific wardrobe pieces to pair
with the new item; with an empty wardrobe, it gives general styling advice (what
kinds of pieces pair well, what vibe it suits).

**What happens if it fails or returns nothing:**
Empty wardrobe is handled as a normal branch (general advice), not an error. If
the LLM call itself fails, the tool returns a descriptive error string rather
than raising, so the loop can still surface something to the user.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion plus item details into a short, shareable OOTD-style
caption for Instagram/TikTok. Uses a higher LLM temperature so repeated calls
read differently.

**Input parameters:**
- `outfit` (str): The styling string returned by `suggest_outfit()`.
- `new_item` (dict): The selected listing (for name, price, platform).

**What it returns:**
A 2–4 sentence casual caption that mentions the item name, price, and platform
once each and captures the outfit vibe in specific terms.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns a descriptive error string
(no LLM call, no exception). If the LLM call fails, returns an error string.

---

### Additional Tools (if any)

None. Scope is the three required tools. Query parsing is handled inline in the
planning loop with regex (see below), not as a separate tool. Possible stretch
tools (not yet built): `parse_query` as a standalone tool, or a `score_listing`
helper extracted from `search_listings`.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The loop is a fixed, linear pipeline — there is no branching on tool choice, only
an early exit on failure. Each step's output is the next step's input:

1. **Parse** the query inline with regex/keyword extraction (no LLM):
   - `max_price`: match `under $30`, `under 30`, `$30`, `<30` → float.
   - `size`: match known size tokens (`XS/S/M/L/XL/XXL`, `US 8`, `W30`, etc.).
   - `description`: the full query string (search scores on keyword overlap, so
     leaving size/price words in is harmless).
2. **Search** with `search_listings(description, size, max_price)`.
   - **If results are empty → set `session["error"]`, return early.** This is the
     only conditional that changes the loop's path.
3. **Select** the top-scored listing as `selected_item`.
4. **Suggest** an outfit with `suggest_outfit(selected_item, wardrobe)`.
5. **Create** the fit card with `create_fit_card(outfit, selected_item)`.
6. **Return** the session.

It knows it's done when the fit card is produced (success) or when search returns
nothing (early exit with an error message).

---

## State Management

**How does information from one tool get passed to the next?**

A single `session` dict (built by `_new_session()`) is the source of truth for
one interaction. Each step writes its result into the session, and later steps
read from it — no globals, no passing long argument lists.

Tracked fields:
- `query` — original user text
- `parsed` — `{description, size, max_price}` from the regex parse
- `search_results` — list returned by `search_listings`
- `selected_item` — the top result, fed to `suggest_outfit` / `create_fit_card`
- `wardrobe` — the user's wardrobe dict (chosen in the UI)
- `outfit_suggestion` — string from `suggest_outfit`
- `fit_card` — string from `create_fit_card`
- `error` — set (and loop exits early) if a step can't continue; `None` on success

Consumers check `session["error"]` first: if set, the other output fields are
`None` and the UI shows only the error.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Returns `[]`; loop sets `session["error"]` with a "broaden your search" message and returns early — LLM tools are never called. |
| suggest_outfit | Wardrobe is empty | Not treated as an error: the tool branches to general styling advice for the item instead of naming wardrobe pieces. (If the LLM call itself errors, it returns a descriptive string.) |
| create_fit_card | Outfit input is missing or incomplete | Guards against empty/whitespace `outfit`, returns a descriptive error string without calling the LLM or raising. |

---

## Architecture

```
        ┌──────────────────────────────────────────────────────────────┐
        │                      Gradio UI (app.py)                       │
        │   query text  +  wardrobe choice  →  handle_query()           │
        └───────────────────────────┬──────────────────────────────────┘
                                     │  run_agent(query, wardrobe)
                                     ▼
        ┌──────────────────────────────────────────────────────────────┐
        │                   Planning Loop (agent.py)                    │
        │                                                                │
        │   _new_session() ──► session dict (shared state) ◄──┐         │
        │        │                                            │         │
        │        ▼                                            │ read/    │
        │   1. parse query (regex)  ── writes parsed ─────────┤ write    │
        │        ▼                                            │         │
        │   2. search_listings() ── writes search_results ───┤         │
        │        │                                            │         │
        │        ├─ empty? ─► set error ─► return early ──────┘         │
        │        ▼ (results)                                            │
        │   3. select top ── writes selected_item ───────────►         │
        │        ▼                                                      │
        │   4. suggest_outfit() ── writes outfit_suggestion ─►         │
        │        ▼                                                      │
        │   5. create_fit_card() ── writes fit_card ─────────►         │
        │        ▼                                                      │
        │   6. return session                                          │
        └───────────────────────────┬──────────────────────────────────┘
                                     │
              ┌──────────────────────┼───────────────────────┐
              ▼                      ▼                        ▼
     search_listings()       suggest_outfit()         create_fit_card()
     (pure Python,           (Groq LLM,               (Groq LLM,
      load_listings)          low temp)                high temp)
```

Trigger summary: search is always step 2; the empty-results check is the only
branch (→ error path). Outfit and fit card run only on the success path. All
state flows through the single `session` dict.

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I'll use **Claude Code** to implement the three tools, one at a time, giving it
the matching Tool section above (inputs, return type, failure mode) plus the
listing/wardrobe field lists from `data_loader.py`.

- `search_listings`: I'll give Claude the Tool 1 spec and ask it to use
  `load_listings()`, do case-insensitive size matching and inclusive price
  filtering, score by keyword overlap against `title + description + style_tags`,
  drop zero-score items, and sort descending. **Verify**: run against
  "vintage graphic tee" (expect tees like lst_002/006/033 ranked high),
  a size filter ("M"), a price ceiling ("under $20"), and the deliberate
  no-results query → must return `[]`.
- `suggest_outfit`: give Claude the Tool 2 spec and the wardrobe schema; confirm
  it branches on empty `items`. **Verify**: run once with the example wardrobe
  (must name real pieces like "baggy straight-leg jeans") and once with the empty
  wardrobe (must give generic advice, never crash).
- `create_fit_card`: give Claude the Tool 3 spec. **Verify**: empty `outfit` →
  error string, valid outfit → 2–4 sentences mentioning name/price/platform; run
  twice to confirm higher temperature produces varied output.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Planning Loop, State Management, and Architecture sections
above and ask it to implement `run_agent()` to match the 7-step flow exactly,
writing each result into the `session` dict and exiting early when
`search_results` is empty. **Verify** with the two cases already in `agent.py`'s
`__main__`: the graphic-tee happy path (error `None`, all fields populated) and
the "designer ballgown size XXS under $5" no-results path (error set, other
fields `None`). Then wire `handle_query()` in `app.py` and run `python app.py`
to confirm the three panels populate and the no-results example shows the error.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** `run_agent` builds a session and parses the query with regex:
`max_price = 30.0` (from "under $30"), `size = None` (no size token present),
`description = ` the full query. Stored in `session["parsed"]`.

**Step 2:** Calls `search_listings("…vintage graphic tee…", None, 30.0)`. Price
filter drops anything over $30; keyword overlap on "vintage/graphic/tee" ranks
the graphic tees highest (e.g. lst_006 "Graphic Tee — 2003 Tour Bootleg Style",
$24; lst_002 "Y2K Baby Tee", $18; lst_033 "Vintage Band Tee", $19). The sorted
list is stored in `session["search_results"]`.

**Step 3:** Results are non-empty, so the loop selects the top result as
`session["selected_item"]` (e.g. lst_006).

**Step 4:** Calls `suggest_outfit(selected_item, example_wardrobe)`. The wardrobe
has items, so the LLM names specific pieces — pairing the graphic tee with the
"Baggy straight-leg jeans" and "Chunky white sneakers" already in the closet.
Stored in `session["outfit_suggestion"]`.

**Step 5:** Calls `create_fit_card(outfit_suggestion, selected_item)`. The LLM
returns a casual 2–4 sentence caption naming the tee, its $24 price, and that
it's on depop. Stored in `session["fit_card"]`.

**Step 6:** Returns the session; `error` is `None`.

**Final output to user:** The three UI panels show — (1) the top listing
(title, price, condition, platform), (2) the outfit idea built from their
wardrobe, and (3) the shareable fit card caption.
