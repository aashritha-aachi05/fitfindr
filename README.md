# FitFindr 🛍️

FitFindr is a tool-using agent that helps you shop secondhand and style what you
find. You describe what you're looking for in plain language ("vintage graphic
tee under $30, size M"); the agent searches a mock listings dataset, picks the
best match, suggests outfits using the clothes you already own, and writes a
shareable "fit card" caption for the find. The whole thing runs behind a Gradio
web UI.

```
"vintage graphic tee under $30"
        │
        ▼
  parse → search_listings → suggest_outfit → create_fit_card
                                │
                                └─ (no matches? stop early with a helpful message)
```

---

## Setup

```bash
pip install -r requirements.txt
```

Add your Groq API key to a `.env` file in the project root (free key at
[console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=gsk_your_key_here
```

Run the app:

```bash
python app.py
```

Then open the localhost URL printed in your terminal (usually
`http://localhost:7860`).

You can also run the agent from the command line without the UI:

```bash
python agent.py
```

---

## Tool Inventory

The agent uses three tools, all defined in `tools.py`. The two LLM-backed tools
call Groq's `llama-3.3-70b-versatile` model.

### 1. `search_listings`

| | |
|---|---|
| **Inputs** | `description: str` — free-text keywords describing the item.<br>`size: str \| None` — size to filter by (case-insensitive substring match; defaults to `None` = no size filter).<br>`max_price: float \| None` — inclusive price ceiling (defaults to `None` = no price filter). |
| **Output** | `list[dict]` — matching listings, sorted by descending relevance score. Each dict is a full listing (`id, title, description, category, style_tags, size, condition, price, colors, brand, platform`). Empty list if nothing matches. |
| **Purpose** | Filter the 40-item mock dataset by size/price, then score each survivor by keyword overlap against its title, style tags, category, description, colors, and brand. This is pure Python — no LLM call — so it's fast and deterministic. Title and style-tag matches are weighted double so the most distinctive fields drive ranking. |

### 2. `suggest_outfit`

| | |
|---|---|
| **Inputs** | `new_item: dict` — the listing the user is considering (the top search result).<br>`wardrobe: dict` — a wardrobe dict with an `items` list (may be empty). |
| **Output** | `str` — a short styling write-up (1–2 outfit ideas). |
| **Purpose** | Ask the LLM to style the new item. If the wardrobe has items, it names specific pieces from the closet ("pair it with your baggy straight-leg jeans and black combat boots") and explains why each combo works. If the wardrobe is empty, it gives general styling advice instead. Uses temperature `0.6` for grounded, consistent suggestions. |

### 3. `create_fit_card`

| | |
|---|---|
| **Inputs** | `outfit: str` — the styling string from `suggest_outfit`.<br>`new_item: dict` — the selected listing (for name, price, platform). |
| **Output** | `str` — a 2–4 sentence casual social caption. |
| **Purpose** | Turn the outfit into a shareable OOTD-style caption that mentions the item name, price, and platform and captures the vibe. Uses a high temperature (`0.95`) so repeated calls read differently. |

---

## How the Planning Loop Works

The loop lives in `run_agent()` (`agent.py`). It's a fixed, linear pipeline where
each step's output feeds the next. The single source of truth is a `session`
dict that every step reads from and writes to.

```
1. Initialize session  ─────────────────────────────► session = _new_session(query, wardrobe)
2. Guard: empty query? ──── yes ──► set error, return early
3. Parse query (regex) ─────────────────────────────► session["parsed"]
4. search_listings()   ─────────────────────────────► session["search_results"]
       │
       └─ empty results? ──── yes ──► set error, return early  ◄── the one real branch
       │
5. Select top result   ─────────────────────────────► session["selected_item"]
6. suggest_outfit()    ─────────────────────────────► session["outfit_suggestion"]
7. create_fit_card()   ─────────────────────────────► session["fit_card"]
8. return session
```

### Conditional logic

There is no LLM-driven "which tool next?" decision — the tool order is fixed.
Two conditions can change the path, and both are early exits:

1. **Empty query** (step 2): if the user submits blank/whitespace, the loop sets
   `session["error"]` and returns immediately. Nothing else runs.
2. **No search results** (step 4): this is the important one. If
   `search_listings` returns `[]`, the loop sets a "broaden your search"
   error and returns **before** calling either LLM tool. This guarantees the
   styling tools never receive empty input. On the success path, results are
   non-empty, so steps 5–7 always have a valid `selected_item` to work with.

The loop knows it's "done" when it produces a fit card (success) or when it hits
one of the two early exits (error).

### Query parsing

Parsing (`_parse_query` in `agent.py`) is regex-based, no LLM:

- **`max_price`** — matches `under $30`, `under 30`, `$30`, `<30`, etc. A number
  is only treated as a price if it's near a price cue (`under`, `below`, `$`, …),
  so `size 8` isn't misread as `$8`.
- **`size`** — matches letter sizes (`XS`–`XXXL`, including `XXS`), prefixed sizes
  (`US 8`, `UK 5`), waist sizes (`W30`, `W30 L30`), and bare shoe sizes
  (`size 8`).
- **`description`** — the full original query. Leaving size/price words in is
  harmless because `search_listings` scores on keyword overlap.

---

## State Management

All state for one interaction lives in a single `session` dict, created by
`_new_session()`. Each step writes its result into the dict; later steps read
from it. No globals, no long argument chains.

| Field | Set by | Holds |
|---|---|---|
| `query` | init | the original user text |
| `parsed` | step 3 | `{description, size, max_price}` |
| `search_results` | step 4 | list returned by `search_listings` |
| `selected_item` | step 5 | the top result (fed to both LLM tools) |
| `wardrobe` | init | the user's wardrobe dict |
| `outfit_suggestion` | step 6 | string from `suggest_outfit` |
| `fit_card` | step 7 | string from `create_fit_card` |
| `error` | any step | message if the loop exited early; `None` on success |

Consumers always check `session["error"]` first. If it's set, the other output
fields are `None` and the UI shows only the error. `app.py`'s `handle_query()`
follows exactly this contract when mapping the session onto the three UI panels.

---

## Error Handling Strategy

The guiding rule: **tools never raise — they return a value the caller can
handle.** Pure-Python failures return empty/sentinel values; LLM failures and
bad input return descriptive strings.

| Tool | Failure mode | What it does | Concrete example |
|---|---|---|---|
| `search_listings` | No listing matches | Returns `[]` (never raises). The loop detects the empty list and sets a "broaden your search" error, skipping the LLM tools entirely. | Query `designer ballgown size XXS under $5` → no match on style/size/price → `[]` → user sees: *"No listings matched that search. Try broadening it — drop the size or price filter, or use more general keywords."* |
| `suggest_outfit` | Wardrobe is empty | Not treated as an error — it's a separate branch that asks the LLM for general styling advice instead of naming closet pieces. | "Empty wardrobe (new user)" selected in the UI → still returns a full paragraph of styling ideas ("pair with high-waisted straight-leg jeans and black-and-white sneakers…") instead of crashing. |
| `suggest_outfit` | Groq API call fails | Wrapped in try/except; returns a descriptive string so the loop can still surface something. | Network/key error → returns `"Could not generate an outfit suggestion right now (<error>)."` |
| `create_fit_card` | `outfit` missing/blank | Guards before any LLM call; returns an explanatory string, no exception. | `create_fit_card("   ", item)` → `"Can't make a fit card without an outfit suggestion — no outfit was provided."` |
| `create_fit_card` | Groq API call fails | Wrapped in try/except; returns a descriptive string. | API error → `"Could not generate a fit card right now (<error>)."` |

The UI layer adds one more guard: an empty/whitespace query returns
*"Please describe what you're looking for."* before the agent even runs.

---

## Spec Reflection

**One way the spec helped.** Writing `planning.md` before any code forced me to
decide the tool contracts up front — especially "`search_listings` returns `[]`,
never raises" and "the only branch in the loop is the empty-results early exit."
Because that was settled on paper, the implementation was almost mechanical: the
loop never has to defensively check whether the LLM tools got valid input,
because the early exit guarantees they don't run on empty results. The
no-results path worked on the first try because it was designed, not patched in.

**One way the implementation diverged.** The spec described query parsing in
broad strokes ("regex for `under $30` / `$30`; regex for size tokens like
`S/M/L/XL`, `US 8`, `W30`"). In practice that wasn't enough. While testing the
example queries I found two gaps the spec hadn't anticipated: `XXS` wasn't in my
size list, and bare shoe sizes like `size 8` weren't matched at all. I also had
to add a "price cue" guard so `size 8` wouldn't be parsed as `$8`. Similarly, the
spec said scoring was "keyword overlap," but the implementation weights title and
style-tag matches double — a refinement I added after seeing that plain overlap
ranked tangential items too highly. The spec set the direction; the edge cases
showed up only in implementation.

---

## AI Usage

I used Claude (via Claude Code) throughout. Two specific instances:

**1. Drafting `planning.md`.** I gave Claude the starter stubs (`tools.py`,
`agent.py`, `app.py`, `data_loader.py`) and two design decisions: parse queries
with **regex/keyword matching, not an LLM**, and ship **only the three required
tools** (no extra `parse_query`/`score_listing` tools). Claude produced the full
planning doc — tool specs, the linear loop with its single early-exit branch, the
error-handling table, an ASCII architecture diagram, and a step-by-step example
interaction. **What I revised:** I went back through the generated doc and edited
it down so it matched how I actually wanted the loop framed, rather than keeping
the AI's first draft verbatim.

**2. Redesigning the Gradio UI.** I told Claude to make `app.py` "look more
modern and visually interesting — better colors, styled components, a custom
theme — but keep the same functionality." Claude added a custom `gr.themes.Soft`
theme (rose/amber/stone + the Poppins font), a gradient hero banner, a grouped
search card, and color-coded result panels. **What I revised — twice:** on first
look the result-panel text was rendering white-on-white (invisible unless
highlighted), because the app was in dark mode while my CSS forced light card
backgrounds. I flagged it and Claude forced dark text on the cards. That exposed
a second instance of the same bug — the query input was now dark-text-on-dark
background — which I also flagged, and Claude fixed by forcing a light input
background plus a readable placeholder color. The lesson was that AI-generated CSS
needs to be checked against the browser's actual (dark) rendering mode, not just
assumed to work.

A third, smaller instance: when Claude first implemented `search_listings` I had
it run the example queries immediately to confirm the ranking made sense
(graphic tees surfacing first for "vintage graphic tee") before trusting the
scoring — and when I asked it to wire up the Groq tools, it caught that my `.env`
held a bare key with no `GROQ_API_KEY=` prefix, which would have silently failed.

---

## Project Structure

```
fitfindr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # wardrobe format + example/empty wardrobes
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), etc.
├── tools.py                   # the three tools
├── agent.py                   # run_agent() planning loop + query parsing
├── app.py                     # Gradio UI + handle_query()
├── planning.md                # design spec (written before implementation)
├── requirements.txt
└── README.md
```
