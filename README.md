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

## Timing (measured)

I/O load JD         : 0.14s
I/O load candidates : 26.12s
Ranking             : 113.38s
I/O write results   : 0.11s
Total               : 139.75s (within 5-min limit)

## Honeypots

0 in top-100. Flagged candidates logged at DEBUG level.

## Architecture

**JD Parser** — regex section matching on "Things you absolutely need" /
"Things we'd like you to have" headers. Extracts required_skills,
preferred_skills, min_yoe, work_mode.

**Scoring (5 dimensions)**
- skill_match (45%) — token Jaccard on normalized skill names,
  proficiency multiplier (0.5→1.0), assessment score bonus
- experience_fit (20%) — Gaussian curve centered at 7yr (midpoint 5-9),
  seniority title bonus, career description keyword scan for prod evidence
- behavioral (22%) — 6 sub-signals: availability recency, responsiveness,
  interview reliability, profile completeness, market demand, github activity
- education (7%) — degree rank × institution tier
- availability (6%) — notice period decay, location bonus (India Tier-1),
  work mode match

**Honeypot detection** — flags expert proficiency + 0 duration_months.
0 honeypots reached top-100.

**Tie-breaking** — equal scores sorted by candidate_id ascending (per spec).

**Runtime** — ~140s total on CPU.
