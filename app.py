"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)
        Each string maps to one of the three output panels in the UI.

    TODO:
        1. Guard against an empty query (return early with an error message).
        2. Select the wardrobe based on wardrobe_choice.
        3. Call run_agent() with the query and selected wardrobe.
        4. If session["error"] is set, return the error in the first panel
           and empty strings for the other two.
        5. Otherwise, format session["selected_item"] into a readable listing_text
           string and return it along with session["outfit_suggestion"] and
           session["fit_card"].
    """
    # 1. Guard against an empty query.
    if not user_query or not user_query.strip():
        return "Please describe what you're looking for.", "", ""

    # 2. Select the wardrobe based on the radio choice.
    wardrobe = (
        get_empty_wardrobe()
        if wardrobe_choice == "Empty wardrobe (new user)"
        else get_example_wardrobe()
    )

    # 3. Run the agent.
    session = run_agent(user_query, wardrobe)

    # 4. On error, show it in the first panel and leave the rest blank.
    if session["error"]:
        return session["error"], "", ""

    # 5. Format the selected listing into a readable block.
    item = session["selected_item"]
    listing_text = (
        f"{item['title']}\n"
        f"${item['price']:.2f} · {item['platform']}\n\n"
        f"Size: {item['size']}\n"
        f"Condition: {item['condition']}\n"
        f"Category: {item['category']}\n"
        f"Style: {', '.join(item['style_tags'])}\n"
        f"Colors: {', '.join(item['colors'])}\n"
        + (f"Brand: {item['brand']}\n" if item.get("brand") else "")
        + f"\n{item['description']}"
    )

    return listing_text, session["outfit_suggestion"], session["fit_card"]


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]


# Warm, editorial "boutique" theme — soft cream canvas, coral→amber accents.
THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.rose,
    secondary_hue=gr.themes.colors.amber,
    neutral_hue=gr.themes.colors.stone,
    font=[gr.themes.GoogleFont("Poppins"), "ui-sans-serif", "system-ui", "sans-serif"],
).set(
    body_background_fill="#faf6f1",
    block_background_fill="#ffffff",
    block_border_width="0px",
    block_shadow="0 6px 22px rgba(120, 80, 60, 0.08)",
    block_radius="18px",
    block_label_text_weight="600",
    input_background_fill="#fffdfb",
    button_large_radius="14px",
    button_primary_text_color="#ffffff",
    button_primary_background_fill="linear-gradient(95deg, #f76b5e 0%, #f9a826 100%)",
    button_primary_background_fill_hover="linear-gradient(95deg, #f9a826 0%, #f76b5e 100%)",
)


CSS = """
.gradio-container { max-width: 1080px !important; margin: 0 auto !important; }

/* ── hero banner ── */
#hero {
    background: linear-gradient(135deg, #f76b5e 0%, #f9a826 100%);
    border-radius: 22px;
    padding: 40px 28px 34px;
    text-align: center;
    color: #fff;
    box-shadow: 0 14px 36px rgba(247, 107, 94, 0.32);
    margin-bottom: 18px;
}
#hero .hero-badge {
    font-size: 2.6rem;
    line-height: 1;
    display: inline-block;
    filter: drop-shadow(0 3px 6px rgba(0,0,0,0.18));
}
#hero h1 {
    font-size: 2.7rem;
    font-weight: 700;
    letter-spacing: -1px;
    margin: 10px 0 6px;
    color: #fff;
}
#hero p {
    font-size: 1.08rem;
    opacity: 0.96;
    margin: 0 auto;
    max-width: 620px;
}

/* ── search card ── */
#search-card {
    background: #fff;
    border-radius: 18px;
    padding: 18px 20px 20px;
    box-shadow: 0 6px 22px rgba(120, 80, 60, 0.08);
    margin-bottom: 8px;
}
#find-btn { font-size: 1.05rem !important; font-weight: 600 !important; padding: 12px 0 !important; }

/* ── output cards: shared + per-panel accent ── */
.out-card { border-top: 5px solid #d8c9bd; padding-top: 4px; }
.out-card textarea {
    font-size: 0.96rem !important;
    line-height: 1.55 !important;
    border-radius: 12px !important;
    color: #2e2620 !important;   /* dark text so it's readable on the light card */
}

/* keep the query box readable too: light background + dark text */
#search-card textarea, #search-card input {
    background: #fffdfb !important;
    color: #2e2620 !important;
}
#search-card textarea::placeholder, #search-card input::placeholder {
    color: #b3a89e !important;
}
#card-listing { border-top-color: #f76b5e; }
#card-listing textarea { background: #fff7f5 !important; }
#card-outfit  { border-top-color: #8b6db5; }
#card-outfit textarea  { background: #f8f5fb !important; }
#card-fit     { border-top-color: #f9a826; }
#card-fit textarea     { background: #fffaf0 !important; }

/* ── section caption ── */
.section-caption { color: #8a7a6d; font-size: 0.95rem; margin: 14px 4px 2px; font-weight: 500; }

footer { display: none !important; }
"""


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.HTML(
            """
            <div id="hero">
                <span class="hero-badge">🛍️</span>
                <h1>FitFindr</h1>
                <p>Discover secondhand gems and style them with the closet you
                already own. Describe what you're after — add a size or price
                to narrow it down.</p>
            </div>
            """
        )

        with gr.Column(elem_id="search-card"):
            with gr.Row(equal_height=True):
                query_input = gr.Textbox(
                    label="What are you looking for?",
                    placeholder="e.g. vintage graphic tee under $30, size M",
                    lines=2,
                    scale=3,
                )
                wardrobe_choice = gr.Radio(
                    choices=["Example wardrobe", "Empty wardrobe (new user)"],
                    value="Example wardrobe",
                    label="👗 Wardrobe",
                    scale=1,
                )
            submit_btn = gr.Button(
                "✨ Find it", variant="primary", size="lg", elem_id="find-btn"
            )

        gr.HTML('<div class="section-caption">Your results</div>')

        with gr.Row(equal_height=True):
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=10,
                interactive=False,
                elem_id="card-listing",
                elem_classes=["out-card"],
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=10,
                interactive=False,
                elem_id="card-outfit",
                elem_classes=["out-card"],
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=10,
                interactive=False,
                elem_id="card-fit",
                elem_classes=["out-card"],
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="✨ Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch(theme=THEME, css=CSS)
