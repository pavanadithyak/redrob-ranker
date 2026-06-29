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

## Timing (5 runs — global Jaccard cache + merged traversals)

| Run | Load Candidates | **Ranking** | **Total** |
|-----|---------------|------------|----------|
| 1 | 43.73s | **65.33s** | 109.24s |
| 2 | 29.23s | **43.13s** | 72.51s |
| 3 | 27.44s | **42.39s** | 70.00s |
| 4 | 25.10s | **65.70s** | 90.84s |
| 5 | 42.97s | **53.93s** | 97.24s |

**Ranking step: ~54s avg (thermal variance 42–66s).** All runs within 5-min limit on CPU-only (1.19 GHz, 16 GB RAM).

## Performance

| Optimization | Impact |
|---|---|
| Global `_SKILL_JACCARD_CACHE` (skill name → best match) | ~58M → ~36K Jaccard calls (1600x) |
| Global `_ASSESS_JACCARD_CACHE` (assessment name → skill entry) | Eliminates per-candidate linear scan |
| Merge `candidate_skills` passes (track `n_beginner_matched` in main loop) | Eliminates second skills iteration |
| Merge `career_history` passes (honeypot checks in experience loop) | Eliminates second career_history iteration |
| Lift JD constants (`_center`, `_n_required`, `_work_mode`, `_pref_locs`) | ~10ms saved per 100k candidates |
| `_TODAY` / `_TODAY_DATE` module-level constants | Eliminates 200K+ OS clock calls |

## Honeypots

0 in top-100. Flagged candidates logged at DEBUG level.

## Architecture

**JD Parser** — regex section matching on "Things you absolutely need" /
"Things we'd like you to have" headers. Extracts required_skills,
preferred_skills, min_yoe, work_mode.

**Scoring (5 dimensions)**
- skill_match (45%) — token Jaccard on normalized skill names with
  global result caching (`_SKILL_JACCARD_CACHE`, ~58M→36K calls),
  proficiency multiplier (0.5→1.0) blended with endorsement confidence
  (max(pw, end/100) for beginner skills), assessment score bonus with
  global name→match cache
- experience_fit (20%) — Gaussian curve centered at 7yr (midpoint 5-9),
  seniority title bonus, precompiled regex scan for prod/retrieval/ranking evidence
- behavioral (22%) — 11 sub-signals: availability recency (20%), response
  rate (14%), interview reliability (14%), profile completeness (14%),
  saved_by_recruiters (10%), github activity (8%), profile views (7%),
  search appearance (5%), applications submitted (4%),
  connection count (2%), endorsements received (2%)
- education (7%) — degree rank × institution tier
- availability (6%) — notice period decay, location bonus (India Tier-1),
  work mode match

**Honeypot detection** — flags: expert+0mo, tenure>600mo,
YOE/career-total mismatch >2yr, future dates in career history.
Checks merged into career_history loop (no second traversal).
0 honeypots reached top-100.

**Tie-breaking** — equal scores sorted by candidate_id ascending (per spec).

## Gradio Space

Try the interactive ranker at https://huggingface.co/spaces/paq1/redrob-ranker

Upload a job description (.txt or .docx) + up to 100 candidate records (.json or .jsonl).
50-record sample at `sample_candidates.jsonl`.
