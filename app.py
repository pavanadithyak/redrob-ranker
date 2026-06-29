import json
import sys
import tempfile
from pathlib import Path

import gradio as gr

from src.ranker import rank_candidates, load_jd_text

CSS = """
body, .gradio-container { background: #F5F0E8 !important; }
.gr-box, .panel { border: none !important; box-shadow: none !important; background: transparent !important; }
h1, h2, h3, label, .gr-text, .prose { font-family: Georgia, 'Times New Roman', serif !important; color: #1a1a1a !important; }
label span { font-size: 0.9rem !important; letter-spacing: 0.02em !important; text-transform: uppercase !important; font-weight: 400 !important; }
button, .gr-button, .gr-button-primary { background: #2D5A27 !important; border: none !important; color: #fff !important; font-family: Georgia, serif !important; font-size: 1rem !important; border-radius: 0 !important; padding: 0.5rem 2rem !important; }
button:hover, .gr-button:hover { background: #1f3f1a !important; }
.gr-dataframe { border: 1px solid #d4c9b8 !important; border-radius: 0 !important; background: #faf7f2 !important; }
.gr-dataframe th { background: #2D5A27 !important; color: #fff !important; font-family: Georgia, serif !important; font-weight: 400 !important; }
.gr-dataframe td { font-family: 'Courier New', monospace !important; font-size: 0.85rem !important; border-color: #e5ddd0 !important; }
footer { display: none !important; }
"""


def load_candidates_bytes(data: bytes) -> list:
    content = data.decode("utf-8").strip()
    if content.startswith("["):
        return json.loads(content)
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def process(jd_file, candidates_file):
    if jd_file is None:
        return "Upload a job description (.txt or .docx)", None
    if candidates_file is None:
        return "Upload a candidates file (.json or .jsonl, max 100 records)", None

    try:
        jd_bytes = jd_file
        if isinstance(jd_bytes, str):
            jd_bytes = Path(jd_bytes).read_bytes()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(jd_bytes)
            tmp_path = tmp.name
        jd_text = load_jd_text(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        return f"Error reading JD: {e}", None

    try:
        candidates_bytes = candidates_file
        if isinstance(candidates_bytes, str):
            candidates_bytes = Path(candidates_bytes).read_bytes()
        candidates = load_candidates_bytes(candidates_bytes)
        if len(candidates) > 100:
            return "Max 100 candidates allowed", None
    except Exception as e:
        return f"Error reading candidates: {e}", None

    try:
        results = rank_candidates(candidates, jd_text, top_n=len(candidates))
    except Exception as e:
        return f"Error during ranking: {e}", None

    rows = [
        [r["rank"], r["candidate_id"], f"{r['score']:.4f}", r["reasoning"]]
        for r in results
    ]
    return None, rows


with gr.Blocks(css=CSS, title="Redrob AI Ranker", theme=gr.themes.Base()) as demo:
    gr.Markdown(
        "# Redrob AI Ranker\n"
        "Score and rank candidates against a Senior AI Engineer job description."
    )
    with gr.Row():
        with gr.Column():
            jd_input = gr.File(label="Job Description (.txt or .docx)", type="binary")
            candidates_input = gr.File(
                label="Candidates (.json or .jsonl, ≤100 records)", type="binary"
            )
            submit_btn = gr.Button("Rank Candidates", variant="primary")
        with gr.Column():
            error_output = gr.Textbox(label="", visible=False)
            output = gr.Dataframe(
                headers=["Rank", "Candidate ID", "Score", "Reasoning"],
                label="Results",
                wrap=True,
            )

    submit_btn.click(
        fn=process,
        inputs=[jd_input, candidates_input],
        outputs=[error_output, output],
    )

    gr.Markdown(
        "---\n"
        "Built for the Redrob AI Challenge | "
        "[GitHub](https://github.com/pavanadithyak/redrob-ranker)"
    )

if __name__ == "__main__":
    demo.launch()
