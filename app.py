import json
import tempfile
from pathlib import Path

import gradio as gr

from src.ranker import rank_candidates, load_jd_text


def load_candidates_bytes(data: bytes) -> list:
    content = data.decode("utf-8").strip()
    if content.startswith("["):
        return json.loads(content)
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def process(jd_file, candidates_file):
    if jd_file is None:
        return gr.update(visible=True, value="Upload a job description (.txt or .docx)"), None
    if candidates_file is None:
        return gr.update(visible=True, value="Upload a candidates file (.json or .jsonl, max 100 records)"), None

    try:
        jd_bytes = jd_file
        if isinstance(jd_bytes, str):
            jd_bytes = Path(jd_bytes).read_bytes()
        suffix = ".docx" if jd_bytes[:2] == b"PK" else ".txt"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(jd_bytes)
            tmp_path = tmp.name
        jd_text = load_jd_text(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        return gr.update(visible=True, value=f"Error reading JD: {e}"), None

    try:
        candidates_bytes = candidates_file
        if isinstance(candidates_bytes, str):
            candidates_bytes = Path(candidates_bytes).read_bytes()
        candidates = load_candidates_bytes(candidates_bytes)
        if len(candidates) > 100:
            return gr.update(visible=True, value="Max 100 candidates allowed"), None
    except Exception as e:
        return gr.update(visible=True, value=f"Error reading candidates: {e}"), None

    try:
        results = rank_candidates(candidates, jd_text, top_n=len(candidates))
    except Exception as e:
        return gr.update(visible=True, value=f"Error during ranking: {e}"), None

    rows = [
        [r["rank"], r["candidate_id"], f"{r['score']:.4f}", r["reasoning"]]
        for r in results
    ]
    return gr.update(visible=False), rows


with gr.Blocks(title="Redrob AI Ranker") as demo:
    gr.Markdown("# Redrob AI Ranker\nScore and rank candidates against a Senior AI Engineer JD.")
    with gr.Row():
        with gr.Column():
            jd_input = gr.File(label="Job Description (.txt or .docx)", type="binary", value="sample_jd.txt")
            candidates_input = gr.File(label="Candidates (.json or .jsonl, max 100)", type="binary")
            btn = gr.Button("Rank Candidates", variant="primary")
        with gr.Column():
            error = gr.HTML(visible=False)
            output = gr.Dataframe(
                headers=["Rank", "Candidate ID", "Score", "Reasoning"],
                label="Results",
                wrap=True,
            )
    btn.click(fn=process, inputs=[jd_input, candidates_input], outputs=[error, output])
    gr.Markdown("---\nBuilt for the Redrob AI Challenge | [GitHub](https://github.com/pavanadithyak/redrob-ranker) | Sample JD pre-loaded — upload candidates to rank.")

if __name__ == "__main__":
    demo.launch()
