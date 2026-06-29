import json
import re
import math
import csv
import sys
import argparse
import heapq
import time
import logging
from pathlib import Path
from datetime import datetime, date

_TODAY = date.today().isoformat()
_TODAY_DATE = date.today()

try:
    from docx import Document
except ImportError:
    Document = None

# Core AI/ML skill keywords that map to the JD requirements
AI_SKILL_KEYWORDS = [
    # ---- JD Required: embeddings, vector search, eval frameworks ----
    "embeddings", "sentence-transformers", "vector database", "faiss",
    "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
    "elasticsearch", "retrieval", "hybrid search", "ndcg", "mrr", "map",
    "evaluation framework", "ranking", "rag",
    # ---- JD Preferred: fine-tuning, learning-to-rank ----
    "langchain", "fine-tuning", "lora", "qlora", "peft",
    "xgboost", "learning to rank",
    # ---- Core tech stack ----
    "python", "pytorch", "tensorflow", "transformers",
    "machine learning", "deep learning", "nlp", "natural language processing",
    "information retrieval", "recommendation system", "search",
    "neural network", "llm", "large language model", "vector search",
    "semantic search", "reranking", "re-ranking",
    "transformer", "bert", "gpt",
    # ---- Production/MLOps ----
    "mlops", "docker", "kubernetes", "aws", "gcp",
    "inference", "model deployment", "model serving",
    "spark", "kafka", "sql",
    "data pipeline", "etl", "data warehouse",
    "flask", "fastapi", "django",
    "scikit-learn", "pandas", "numpy",
    "mlflow", "kubeflow",
    "api", "microservice",
    "production", "deployment",
]

REQUIRED_JD_HEADERS = [
    "things you absolutely need", "things we absolutely need",
    "must have", "requirements", "required",
]
PREFERRED_JD_HEADERS = [
    "things we'd like you to have", "things we would like you to have",
    "nice to have", "preferred", "bonus", "good to have",
]
ANTI_JD_HEADERS = [
    "things we explicitly do not want", "do not want",
    "not a fit", "disqualifiers", "anti-requirements",
]
_RETRIEVAL_RE = re.compile(r'(?:embedding|retrieval|vector|search|semantic|similarity|faiss|pinecone|weaviate|qdrant|milvus)')
_RANKING_RE = re.compile(r'(?:ranking|ranker|recommend|ndcg|mrr|map|learning to rank)')
_PROD_RE = re.compile(r'(?:production|deployed|shipped|launched|live|scal)')
CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "hcl", "tech mahindra", "mindtree", "ltts",
    "mphasis", "hexaware", "cyient", "persistent", "zensar",
}

_NORM_CACHE = {}

def _normalize_tokens(text):
    if text in _NORM_CACHE:
        return _NORM_CACHE[text]
    t = text.lower()
    t = re.sub(r'[^\w\s/-]', ' ', t)
    t = re.sub(r'\s*[-/]\s*', ' ', t)
    tokens = [w for w in t.split() if len(w) > 1]
    _NORM_CACHE[text] = tokens
    return tokens


def _token_set(text):
    return set(_normalize_tokens(text))


def _jaccard(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    return inter / (len(set_a) + len(set_b) - inter)


ALL_JD_HEADERS = REQUIRED_JD_HEADERS + PREFERRED_JD_HEADERS + ANTI_JD_HEADERS

def _extract_all_sections(text):
    lines = text.split('\n')
    sections = {}
    current_key = None
    current_lines = []
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        matched_header = None
        for marker in ALL_JD_HEADERS:
            if marker in lower:
                matched_header = marker
                break
        if matched_header:
            if current_key and current_lines:
                sections[current_key] = '\n'.join(current_lines).strip()
            current_key = matched_header
            current_lines = []
        elif current_key:
            current_lines.append(stripped)
    if current_key and current_lines:
        sections[current_key] = '\n'.join(current_lines).strip()
    return sections


def _parse_bullets(text, stop_headers=None):
    items = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if stop_headers and any(h in line.lower() for h in stop_headers):
            break
        if re.match(r'^[\s]*[-•*–]', line):
            items.append(re.sub(r'^[\s]*[-•*–]\s*', '', line).strip())
        elif re.match(r'^\d+[.)]', line):
            items.append(re.sub(r'^\d+[.)]\s*', '', line).strip())
        else:
            items.append(line)
    return items


def _extract_keywords_from_bullets(bullets):
    keywords = []
    for bullet in bullets:
        lower = bullet.lower()
        for kw in AI_SKILL_KEYWORDS:
            if kw in lower:
                keywords.append(kw)
    return keywords


def parse_jd(text):
    result = {
        "required_keywords": [],
        "preferred_keywords": [],
        "anti_patterns": [],
        "min_yoe": 5, "max_yoe": 9,
        "preferred_locations": ["pune", "noida", "hyderabad", "mumbai", "delhi ncr"],
        "work_mode": "hybrid", "salary": {},
    }
    exp_match = re.search(r'(\d+)[–\-]\s*(\d+)\s*years?', text)
    if exp_match:
        result["min_yoe"] = int(exp_match.group(1))
        result["max_yoe"] = int(exp_match.group(2))

    all_sections = _extract_all_sections(text)

    for marker in REQUIRED_JD_HEADERS:
        if marker in all_sections:
            bullets = _parse_bullets(all_sections[marker])
            result["required_keywords"].extend(_extract_keywords_from_bullets(bullets))

    for marker in PREFERRED_JD_HEADERS:
        if marker in all_sections:
            bullets = _parse_bullets(all_sections[marker])
            result["preferred_keywords"].extend(_extract_keywords_from_bullets(bullets))

    for marker in ANTI_JD_HEADERS:
        if marker in all_sections:
            bullets = _parse_bullets(all_sections[marker])
            result["anti_patterns"].extend(bullets)

    result["required_keywords"] = list(set(result["required_keywords"]))
    result["preferred_keywords"] = list(set(result["preferred_keywords"]))
    return result


def _build_skill_index(jd):
    all_keywords = jd["required_keywords"] + jd["preferred_keywords"]
    required_set = set(jd["required_keywords"])
    entries = []
    for kw in all_keywords:
        st = _token_set(kw)
        if st:
            entries.append((kw, st, kw in required_set))
    for kw in AI_SKILL_KEYWORDS:
        if kw not in all_keywords:
            st = _token_set(kw)
            if st:
                entries.append((kw, st, False))
    return entries


_PROF_WEIGHTS = {"expert": 1.0, "advanced": 0.9, "intermediate": 0.75, "beginner": 0.5}
_DEGREE_RANK = {"phd": 1.0, "ph.d": 1.0, "doctorate": 1.0, "master": 0.8, "m.sc": 0.8,
                "m.tech": 0.8, "m.e.": 0.8, "mba": 0.8, "bachelor": 0.6, "b.sc": 0.6,
                "b.tech": 0.6, "b.e.": 0.6}
_TIER_RANK = {"tier_1": 1.0, "tier_2": 0.8, "tier_3": 0.6, "tier_4": 0.4, "unknown": 0.3}


def _proficiency_weight(p):
    return _PROF_WEIGHTS.get(p.lower(), 0.5)


def _degree_rank(d):
    dl = (d or "").lower()
    for key, val in _DEGREE_RANK.items():
        if key in dl:
            return val
    return 0.3


def _tier_rank(t):
    return _TIER_RANK.get(t, 0.3)


def _is_honeypot(candidate):
    skills = candidate.get("skills", [])
    if not skills:
        return False
    expert_zero = sum(
        1 for s in skills
        if s and (s.get("proficiency") or "").lower() == "expert" and s.get("duration_months", -1) == 0
    )
    if expert_zero > 0:
        return True
    total = len(skills)
    if total >= 8 and expert_zero >= total * 0.5:
        return True
    for entry in candidate.get("career_history", []):
        if entry.get("duration_months", 0) > 600:
            return True

    # YOE vs career total mismatch
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    total_career_months = sum(e.get("duration_months", 0) for e in candidate.get("career_history", []))
    if yoe > 0 and total_career_months > yoe * 12 + 24:
        return True
    if yoe > 0 and total_career_months > 0 and total_career_months < yoe * 12 - 24:
        return True

    # Future dates
    today = _TODAY
    for entry in candidate.get("career_history", []):
        sd = entry.get("start_date", "")
        ed = entry.get("end_date", "")
        if (sd and sd > today) or (ed and ed > today):
            return True

    return False


def score_candidate(candidate, jd, skill_index):
    profile = candidate.get("profile", {})
    career_history = candidate.get("career_history", [])
    education_list = candidate.get("education", [])
    rs = candidate.get("redrob_signals", {})

    # ---- skill_match (45%) ----
    candidate_skills = candidate.get("skills", [])
    skill_score = 0.0
    if candidate_skills:
        matches = []
        _matched = {}
        for s in candidate_skills:
            name = s.get("name", "")
            if not name:
                continue
            c_set = _token_set(name)
            if not c_set:
                continue
            pw = _proficiency_weight(s.get("proficiency", "beginner"))
            dur = s.get("duration_months", 0)
            end = s.get("endorsements", 0)

            cached = _matched.get(name)
            if cached:
                best, best_is_required = cached
            else:
                best = 0.0
                best_is_required = False
                for _, js_set, is_req in skill_index:
                    sim = _jaccard(c_set, js_set)
                    if sim > best:
                        best = sim
                        best_is_required = is_req
                        if best >= 0.6:
                            break
                _matched[name] = (best, best_is_required)

            if best > 0.2:
                db = min(dur / 120, 0.1)
                weight = 1.5 if best_is_required else 1.0
                confidence = min(end / 100, 0.4)
                adj_pw = max(pw, confidence)
                adjusted = min(best * adj_pw * weight + db, 1.0)
                matches.append(adjusted)

        if matches:
            matches.sort(reverse=True)
            n = len(matches)
            base = sum(matches) / n
            n_required = len(jd["required_keywords"])
            if n_required > 0:
                coverage_frac = n / (n_required * 2)
                base += min(coverage_frac * 0.3, 0.15)

            beginner_matches = sum(
                1 for s in candidate_skills
                if s.get("name") and _proficiency_weight(s.get("proficiency", "beginner")) <= 0.5
                and _matched.get(s["name"], (0, False))[0] > 0.3
            )
            if matches and beginner_matches / len(matches) > 0.6:
                base *= 0.6

            as_scores = rs.get("skill_assessment_scores", {})
            if as_scores:
                total_a = 0
                match_a = 0.0
                for an, av in as_scores.items():
                    a_set = _token_set(an)
                    if not a_set:
                        continue
                    _, js_set, _ = next(
                        (x for x in skill_index if _jaccard(a_set, x[1]) > 0.5),
                        (None, None, None)
                    )
                    if js_set is not None:
                        match_a += av / 100.0
                    total_a += 1
                if total_a > 0:
                    base += (match_a / total_a) * 0.15

            skill_score = min(base, 1.0)

    # ---- experience_fit (20%) ----
    yoe = profile.get("years_of_experience", 0)
    center = (jd["min_yoe"] + jd["max_yoe"]) / 2.0
    yoe_score = math.exp(-0.5 * ((yoe - center) / 3.0) ** 2)
    title = (profile.get("current_title") or "").lower()
    seniority_bonus = 0.0
    if any(t in title for t in ["senior", "lead", "staff", "principal", "head", "chief"]):
        seniority_bonus = 0.15
    if any(t in title for t in ["engineer", "developer", "architect", "scientist", "researcher"]):
        seniority_bonus += 0.05

    has_retrieval = False
    has_ranking = False
    has_prod = False
    has_product_co = False
    consulting_only = True
    for entry in career_history:
        desc = (entry.get("description") or "").lower()
        co = (entry.get("company") or "").lower()
        if _RETRIEVAL_RE.search(desc):
            has_retrieval = True
        if _RANKING_RE.search(desc):
            has_ranking = True
        if _PROD_RE.search(desc):
            has_prod = True
        if not any(ck in co for ck in CONSULTING_FIRMS):
            has_product_co = True
    if has_product_co:
        consulting_only = False

    depth_bonus = 0.0
    if has_retrieval:
        depth_bonus += 0.15
    if has_ranking:
        depth_bonus += 0.10
    if has_prod:
        depth_bonus += 0.10
    consulting_penalty = 0.20 if consulting_only and len(career_history) > 0 else 0.0
    exp_score = max(min(yoe_score + seniority_bonus + depth_bonus - consulting_penalty, 1.0), 0.0)

    # ---- behavioral (22%) ----
    bs = 0.0
    if rs:
        o2w = 1.0 if rs.get("open_to_work_flag") else 0.0
        last_active_str = rs.get("last_active_date", "")
        recency = 0.0
        days_since = 999
        if last_active_str:
            try:
                la = datetime.strptime(last_active_str, "%Y-%m-%d").date()
                days_since = (_TODAY_DATE - la).days
                recency = 1.0 / (1.0 + math.exp((days_since - 90) / 30))
            except ValueError:
                pass
        rr = rs.get("recruiter_response_rate", 0)
        art = rs.get("avg_response_time_hours", 168)
        rts = max(0, 1.0 - (art / 336))
        rc = rr * 0.7 + rts * 0.3
        icr = rs.get("interview_completion_rate", 0)
        oar = rs.get("offer_acceptance_rate", -1)
        if oar == -1:
            oar = 0.5
        ic = icr * 0.6 + oar * 0.4
        comp = rs.get("profile_completeness_score", 0) / 100.0
        ve = 0.15 if rs.get("verified_email") else 0.0
        vp = 0.10 if rs.get("verified_phone") else 0.0
        li = 0.05 if rs.get("linkedin_connected") else 0.0
        vc = min(comp + ve + vp + li, 1.0)
        saved = rs.get("saved_by_recruiters_30d", 0)
        es = math.log10(max(1, saved)) / 3.0
        gh = rs.get("github_activity_score", -1)
        gs = max(0, gh / 100.0) if gh >= 0 else 0.0
        ip = 0.0
        if rr < 0.1 and days_since > 90:
            ip = 0.3
        if not o2w and days_since > 60:
            ip = max(ip, 0.2)
        comps = [(o2w * 0.5 + recency * 0.5), rc, ic, vc, min(es, 1.0), gs]
        bs = max(min(sum(comps) / len(comps) - ip, 1.0), 0.0)

    # ---- education (7%) ----
    edu_score = 0.0
    if education_list:
        scores = [_degree_rank(e.get("degree", "")) * _tier_rank(e.get("tier", "unknown"))
                  for e in education_list]
        if scores:
            edu_score = max(scores)

    # ---- availability (6%) ----
    avail_score = 0.0
    if rs:
        notice = rs.get("notice_period_days", 90)
        ns = 1.0 if notice <= 30 else (0.7 if notice <= 60 else (0.4 if notice <= 90 else 0.2))
        wm = (rs.get("preferred_work_mode") or "").lower()
        jd_wm = jd.get("work_mode", "hybrid").lower()
        ms = 1.0 if wm == jd_wm else (0.9 if wm == "flexible" else (0.7 if wm == "remote" else (0.8 if wm == "onsite" else 0.6)))
        loc = (profile.get("location") or "").lower()
        co = (profile.get("country") or "").lower()
        lb = -0.15 if co != "india" else (0.15 if any(p in loc for p in jd["preferred_locations"]) else 0.0)
        if rs.get("willing_to_relocate"):
            lb += 0.05
        sal = rs.get("expected_salary_range_inr_lpa", {})
        sal_align = 0.5
        if sal and "min" in sal and "max" in sal:
            smin, smax = sal["min"], sal["max"]
            if 10 <= smin <= 50 and 20 <= smax <= 80:
                sal_align = 1.0
            elif 5 <= smin <= 60 and 10 <= smax <= 100:
                sal_align = 0.8
        avail_score = min(ns * 0.4 + ms * 0.2 + max(0, 1.0 + lb) * 0.2 + sal_align * 0.2, 1.0)

    total = 0.45 * skill_score + 0.20 * exp_score + 0.22 * bs + 0.07 * edu_score + 0.06 * avail_score
    is_hp = _is_honeypot(candidate)
    if is_hp:
        total *= 0.3

    return {
        "scores": {
            "skill_match": round(skill_score, 4),
            "experience_fit": round(exp_score, 4),
            "behavioral": round(bs, 4),
            "education": round(edu_score, 4),
            "availability": round(avail_score, 4),
        },
        "total": round(total, 4),
        "honeypot": is_hp,
        "has_prod": has_prod,
    }


def _generate_reasoning(candidate, sr, rank):
    profile = candidate.get("profile", {})
    rs = candidate.get("redrob_signals", {})
    skills = candidate.get("skills", [])
    title = profile.get("current_title", "Professional")
    yoe = profile.get("years_of_experience", 0)
    scores = sr["scores"]

    top_skills = [s.get("name", "") for s in skills[:3] if s.get("name")]
    skill_str = "/".join(top_skills) if top_skills else "general"

    concerns = []
    if scores.get("availability", 1) < 0.5:
        concerns.append(f"notice {rs.get('notice_period_days', 0)}d")
    if scores.get("behavioral", 1) < 0.4:
        concerns.append(f"low engagement (resp={rs.get('recruiter_response_rate', 0)})")
    if sr.get("honeypot"):
        concerns.append("profile inconsistency flagged")
    loc = profile.get("location", "")
    if (profile.get("country") or "").lower() != "india":
        concerns.append(f"non-India ({loc})")

    current_co = profile.get("current_company", "")
    has_prod = sr.get("has_prod", False)

    concern_str = concerns[0] if concerns else "no major concerns"
    if rank <= 10:
        if has_prod and current_co:
            return f"{title}, {yoe}yr; strong on {skill_str} at {current_co}. {concern_str}."[:200]
        return f"{title}, {yoe}yr; strong on {skill_str}. {concern_str}."[:200]
    elif rank <= 50:
        return f"{title}, {yoe}yr; {skill_str}. {concern_str}."[:200]
    else:
        if concerns:
            return f"{title}, {yoe}yr; {concerns[0]}. Adjacent fit via {skill_str}."[:200]
        return f"{title}, {yoe}yr; {skill_str}. Marginal fit."[:200]


def rank_candidates(candidates, jd_text, top_n=100):
    jd = parse_jd(jd_text)
    skill_index = _build_skill_index(jd)

    heap = []
    honeypots_in_top = 0
    total_scored = 0

    for candidate in candidates:
        sr = score_candidate(candidate, jd, skill_index)
        total_scored += 1
        total = sr["total"]
        cid = candidate.get("candidate_id", "")
        if sr["honeypot"]:
            logging.debug("Honeypot flagged: candidate_id=%s | expert+0mo or tenure>600mo or expert_zero>=50%%", cid)
        if len(heap) < top_n:
            heapq.heappush(heap, (total, cid, candidate, sr))
        elif total > heap[0][0]:
            heapq.heapreplace(heap, (total, cid, candidate, sr))
        if total_scored % 25000 == 0:
            print(f"  Scored {total_scored} candidates...", file=sys.stderr)

    items = sorted(heap, key=lambda x: (-x[0], x[1]))
    results = []
    for rank, (total, cid, candidate, sr) in enumerate(items, start=1):
        reasoning = _generate_reasoning(candidate, sr, rank)
        if sr["honeypot"]:
            honeypots_in_top += 1
        results.append({
            "candidate_id": cid,
            "rank": rank,
            "score": total,
            "reasoning": reasoning,
        })
    print(f"  Scored {total_scored} candidates total", file=sys.stderr)
    print(f"  Honeypots in top {top_n}: {honeypots_in_top}", file=sys.stderr)
    return results


def load_jd_text(jd_path):
    path = Path(jd_path)
    if path.suffix.lower() == ".docx":
        if Document is None:
            raise ImportError("python-docx required for .docx files")
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1252")


def load_candidates(candidates_path):
    path = Path(candidates_path)
    content = None
    if path.suffix.lower() == ".gz":
        import gzip
        with gzip.open(str(path), "rt", encoding="utf-8") as f:
            content = f.read()
    else:
        content = path.read_text(encoding="utf-8")
    content = content.strip()
    if content.startswith("["):
        return json.loads(content)
    return [json.loads(line) for line in content.split("\n") if line.strip()]


def write_submission(results, out_path):
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for r in results:
            w.writerow([r["candidate_id"], r["rank"], f"{r['score']:.4f}", r["reasoning"]])


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    p = argparse.ArgumentParser(description="Redrob Candidate Ranker")
    p.add_argument("--candidates", required=True)
    p.add_argument("--jd", default="./job_description.docx")
    p.add_argument("--out", default="./submission.csv")
    p.add_argument("--top-n", type=int, default=100)
    args = p.parse_args()

    t0 = time.perf_counter()

    print("Loading JD...", file=sys.stderr)
    jd_text = load_jd_text(args.jd)
    t1 = time.perf_counter()

    print("Loading candidates...", file=sys.stderr)
    candidates = load_candidates(args.candidates)
    t2 = time.perf_counter()
    print(f"  Loaded {len(candidates)} candidates", file=sys.stderr)

    print("Ranking...", file=sys.stderr)
    results = rank_candidates(candidates, jd_text, top_n=args.top_n)
    t3 = time.perf_counter()

    print(f"Writing {args.out}...", file=sys.stderr)
    write_submission(results, args.out)
    t4 = time.perf_counter()

    print(f"[benchmark] I/O load JD: {t1 - t0:.2f}s", file=sys.stderr)
    print(f"[benchmark] I/O load candidates: {t2 - t1:.2f}s", file=sys.stderr)
    print(f"[benchmark] Ranking (score all + heap select): {t3 - t2:.2f}s", file=sys.stderr)
    print(f"[benchmark] I/O write results: {t4 - t3:.2f}s", file=sys.stderr)
    print(f"[benchmark] Total: {t4 - t0:.2f}s", file=sys.stderr)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
