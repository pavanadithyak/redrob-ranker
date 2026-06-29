---
title: Redrob AI Ranker
sdk: gradio
app_file: app.py
pinned: false
---

# Redrob AI Challenge — Candidate Ranker

## Reproduce

```
python rank.py --candidates candidates.jsonl --jd job_description.docx --out submission.csv
```

## Timing (5 cold-start runs)

| Run | JD Load | Load Candidates | **Ranking** | Write | **Total** |
|-----|---------|----------------|------------|-------|----------|
| 1 | 0.13s | 16.88s | **56.45s** | 0.22s | 73.68s |
| 2 | 0.03s | 15.31s | **59.51s** | 0.00s | 74.85s |
| 3 | 0.13s | 12.36s | **53.22s** | 0.00s | 65.71s |
| 4 | 0.03s | 13.41s | **57.87s** | 0.00s | 71.31s |
| 5 | 0.03s | 10.56s | **55.32s** | 0.00s | 65.91s |

**Ranking step: ~56s avg.** Total under 5-min limit on CPU-only (1.19 GHz, 16 GB RAM).

## Honeypots

0 in top-100. Flagged candidates logged at DEBUG level.

## Architecture

**JD Parser** — regex section matching on "Things you absolutely need" /
"Things we'd like you to have" headers. Extracts required_skills,
preferred_skills, min_yoe, work_mode.

**Scoring (5 dimensions)**
- skill_match (45%) — token Jaccard on normalized skill names with
  result caching (`_matched` dict), proficiency multiplier (0.5→1.0)
  blended with endorsement confidence (max(pw, end/100) for beginner skills),
  assessment score bonus
- experience_fit (20%) — Gaussian curve centered at 7yr (midpoint 5-9),
  seniority title bonus, precompiled regex scan for prod/retrieval/ranking evidence
- behavioral (22%) — 5 sub-signals: availability recency, responsiveness,
  interview reliability, profile completeness, saved_by_recruiters_30d,
  github activity (views & search_appearance dropped — correlated)
- education (7%) — degree rank × institution tier
- availability (6%) — notice period decay, location bonus (India Tier-1),
  work mode match

**Honeypot detection** — flags: expert+0mo, tenure>600mo,
YOE/career-total mismatch >2yr, future dates in career history.
0 honeypots reached top-100.

**Tie-breaking** — equal scores sorted by candidate_id ascending (per spec).

## Gradio Space

Try the interactive ranker at https://huggingface.co/spaces/paq1/redrob-ranker

Upload a job description (.txt or .docx) + up to 100 candidate records (.json or .jsonl).
A 50-record sample is included at `sample_candidates.jsonl`.
