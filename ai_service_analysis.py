"""AI service functions split out of ai_services.py."""

from _ai_service_common import *

# Moved from ai_services.py: analyze_ai_likelihood
def analyze_ai_likelihood(transcript, job_title):
    """Estimate the probability that a candidate's interview answers were
    AI-generated (e.g. typed into ChatGPT and read aloud) rather than authentic.
    Returns a dict: {score: 0-100, label: str, reasons: [str]}"""
    candidate_lines = []
    for line in transcript.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("user:"):
            candidate_lines.append(stripped[5:].strip())

    if not candidate_lines:
        return {"score": 0, "label": "No data", "reasons": []}

    candidate_text = "\n\n".join(candidate_lines)

    prompt = f"""You are a hiring expert analyzing job interview answers to detect whether they were AI-generated (e.g. the candidate used ChatGPT to write answers and read or pasted them) rather than authentic spoken responses.

Job: {job_title}

Candidate's answers only:
{candidate_text[:3000]}

Analyze for these specific AI signals:
1. Formulaic structure (e.g. "First I would X, then Y, finally Z" repeated across answers)
2. Dense corporate buzzwords used unnaturally ("leverage", "synergize", "holistic approach", "proactive mindset")
3. Suspiciously comprehensive coverage — real humans miss things; AI answers every angle
4. Missing personal specifics — no real names, company names, concrete dates, or actual numbers from memory
5. Zero natural speech disfluencies — no self-corrections, incomplete thoughts, or casual phrasing
6. Answers that parrot the question's exact wording back verbatim
7. Eerily consistent tone, vocabulary level, and answer length across all questions
8. Vague experience claims without supporting detail ("I have extensive experience in X")

Score 0-100 where 0 = clearly authentic human speech and 100 = almost certainly AI-generated or heavily AI-edited.
Give 3 specific reasons citing actual phrases or patterns from the text above.

Respond EXACTLY in this format (no extra text):
Score: <number>
Reason: <one specific observation — quote or name a phrase from the answers>
Reason: <another specific observation>
Reason: <another specific observation>"""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=350,
        temperature=0.2,
    )
    content = response.choices[0].message.content.strip()

    result = {"score": 0, "label": "Human-like", "reasons": []}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Score:"):
            try:
                result["score"] = min(100, max(0, int(re.search(r"\d+", line).group())))
            except Exception:
                pass
        elif line.startswith("Reason:"):
            result["reasons"].append(line[7:].strip())

    score = result["score"]
    if score < 35:
        result["label"] = "Human-like"
    elif score < 65:
        result["label"] = "Uncertain"
    else:
        result["label"] = "Likely AI-assisted"

    return result

# Moved from ai_services.py: analyze_platform_feedback
def analyze_platform_feedback(feedback_rows):
    """Summarize a batch of candidate/employer feedback (rating + comment) into
    a short overview plus specific, actionable recommendations for admins to
    review - this only produces suggestions, it never changes anything itself.
    feedback_rows: list of {role, context, rating, comment} dicts.
    Returns {summary: str, recommendations: [{title, detail}]}."""
    if not feedback_rows:
        return {"summary": "No feedback yet.", "recommendations": []}

    avg_rating = sum(r["rating"] for r in feedback_rows) / len(feedback_rows)

    lines = []
    for r in feedback_rows[:200]:
        comment = (r.get("comment") or "").strip().replace("\n", " ")
        lines.append(f"[{r['role']} | {r['context']} | {r['rating']}/5] {comment or '(no comment)'}")
    feedback_text = "\n".join(lines)

    prompt = f"""You are analyzing user feedback for an AI-powered hiring platform (candidates apply, get AI-interviewed, \
get scored; employers post jobs and review AI-screened applicants). Below is a batch of {len(feedback_rows)} feedback \
entries from candidates and employers, average rating {avg_rating:.1f}/5.

{feedback_text[:8000]}

Identify real, recurring patterns - not one-off complaints. Write a short overall summary, then 2-5 specific, \
actionable recommendations. Each recommendation must name a concrete, viable change (not vague advice like "improve \
communication") and say which group it's based on (candidates, employers, or both). If the feedback is too sparse or \
inconsistent to support a confident recommendation, say so instead of inventing one.

Respond EXACTLY in this format:
Summary: <2-3 sentences on the overall picture>

Recommendation: <short title (4-8 words)>
Based on: <candidates / employers / both>
Detail: <1-2 sentences - the specific, concrete change and why the feedback supports it>

Recommendation: ...
Based on: ...
Detail: ..."""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.3,
    )
    content = response.choices[0].message.content.strip()

    summary = ""
    recommendations = []
    current = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Summary:"):
            summary = line[8:].strip()
        elif line.startswith("Recommendation:"):
            if current and current.get("title"):
                recommendations.append(current)
            current = {"title": line[16:].strip(), "based_on": "", "detail": ""}
        elif line.startswith("Based on:") and current is not None:
            current["based_on"] = line[9:].strip()
        elif line.startswith("Detail:") and current is not None:
            current["detail"] = line[7:].strip()
    if current and current.get("title"):
        recommendations.append(current)

    return {"summary": summary or content[:400], "recommendations": recommendations[:5]}

