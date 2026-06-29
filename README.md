---
title: Redrob AI Ranker
emoji: 🏆
colorFrom: "green"
colorTo: "gray"
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

I/O load JD         : 0.08s
I/O load candidates : 25.47s
Ranking             : 97.06s  (was 113s; cached Jaccard + precompiled regex)
I/O write results   : 0.00s
Total               : 122.62s (within 5-min limit)

## Honeypots

0 in top-100. Flagged candidates logged at DEBUG level.
Checks: expert+0mo, tenure>600mo, YOE mismatch >2yr, future dates.

## Architecture

**JD Parser** — regex section matching on "Things you absolutely need" /
"Things we'd like you to have" headers. Extracts required_skills,
preferred_skills, min_yoe, work_mode.

**Scoring (5 dimensions)**
- skill_match (45%) — token Jaccard on normalized skill names with
  result caching (_NORM_CACHE, _matched), proficiency multiplier (0.5→1.0)
  blended with endorsement confidence (max(pw, end/100) for beginner skills),
  assessment score bonus
- experience_fit (20%) — Gaussian curve centered at 7yr (midpoint 5-9),
  seniority title bonus, career description regex scan for prod evidence,
  precompiled _RETRIEVAL_RE / _RANKING_RE / _PROD_RE
- behavioral (22%) — saved_by_recruiters_30d (views & search_appearance
  dropped — correlated); availability recency, responsiveness,
  interview reliability, profile completeness, github activity
- education (7%) — degree rank × institution tier
- availability (6%) — notice period decay, location bonus (India Tier-1),
  work mode match

**Honeypot detection** — expert+0mo, tenure>600mo, YOE/career mismatch >2yr,
future dates in career history. 0 honeypots reached top-100.

**Tie-breaking** — equal scores sorted by candidate_id ascending (per spec).
