"""AI service functions split out of ai_services.py."""

from _ai_service_common import *

# Moved from ai_services.py: generate_interview_coaching
def generate_interview_coaching(transcript, job_title, requirements, verdict, match_score, resume=None):
    """Analyze a candidate's interview transcript and produce a private coaching report.
    Returns a dict with: communication_score, strengths (list), improvements (list), tips (list).
    Raises ValueError if the model's output doesn't parse into a usable report - callers
    should treat that as "temporarily unavailable," not silently show a fabricated score.

    When a resume is supplied, the model is also asked to cross-check what was actually
    said against what the resume claims - flagging unsupported or inflated claims as an
    Improvement rather than just grading communication style in isolation."""
    resume_block = (
        f"\nCandidate's resume (verify their answers against this - flag anything they "
        f"claimed in the interview that isn't backed up here, or that contradicts it):\n"
        f"{resume[:2000]}\n"
    ) if resume else ""

    prompt = f"""You are a strict, critical communication coach analyzing a job interview. Your report is private and shown only to the candidate who gave this interview - address THEM directly throughout as "you"/"your", never in the third person as "the candidate" or "they". Grade rigorously: most real candidates should NOT score above 75. Do not be encouraging or generous — an unspecific, rambling, or filler-heavy answer is a weak answer regardless of confidence or tone.

Job: {job_title}
Requirements: {(requirements or '')[:400]}
AI verdict: {verdict or 'Not yet determined'}
Match score: {match_score}/100 (0–100 scale)
{resume_block}
Interview transcript:
{transcript[:3000]}

Produce a coaching report with:
1. A Communication Score (0–100) based on confidence, clarity, depth, and specificity. Score anchors:
   - 90-100: exceptional — every answer specific, quantified, and directly relevant. Rare.
   - 70-89: solid — mostly specific with concrete examples, a few vague moments.
   - 50-69: mixed — some substance but noticeably vague, generic, or unfocused answers.
   - Below 50: weak — mostly vague, evasive, filler-heavy, or off-topic answers.
2. A Detailed Analysis - 4-6 sentences of real prose (not bullets), written directly to the candidate as "you", giving a fuller narrative assessment: what your answer(s) actually covered, how specific vs. generic you were, and how that lines up with what this role needs.
3. Exactly 2-3 Strengths — each MUST quote or closely paraphrase a specific moment from the transcript, addressed to "you" (e.g. "You gave a concrete example when you described..."). Do not invent generic strengths ("good communicator") with no textual basis.
4. Exactly 2-3 Improvements — concrete, specific gaps tied to your actual answers, addressed to "you", not generic advice like "be more confident."{" At least one Improvement MUST address any claim in the transcript that your resume doesn't support or contradicts, if one exists." if resume else ""}
5. Exactly 2-3 actionable Tips for your next interview, addressed to "you", specific to the gaps identified above.

If the transcript is too short or low-effort to support a real assessment, say so honestly to the candidate with a low score rather than padding the report.

Respond EXACTLY in this format, with no extra commentary:
CommunicationScore: <number>
DetailedAnalysis: <4-6 sentences of prose, addressed to "you">
Strength: <1 sentence referencing something specific you said>
Strength: <1 sentence>
Improvement: <1 sentence identifying a specific gap>
Improvement: <1 sentence>
Tip: <1 sentence, concrete and actionable>
Tip: <1 sentence>
Tip: <1 sentence>"""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.2,
    )
    content = response.choices[0].message.content.strip()

    result = {
        "communication_score": None,
        "detailed_analysis": None,
        "strengths": [],
        "improvements": [],
        "tips": [],
    }
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("CommunicationScore:"):
            match = re.search(r"\d+", line)
            if match:
                result["communication_score"] = max(0, min(100, int(match.group())))
        elif line.startswith("DetailedAnalysis:"):
            result["detailed_analysis"] = line[18:].strip()
        elif line.startswith("Strength:"):
            result["strengths"].append(line[9:].strip())
        elif line.startswith("Improvement:"):
            result["improvements"].append(line[12:].strip())
        elif line.startswith("Tip:"):
            result["tips"].append(line[4:].strip())

    if (result["communication_score"] is None or not result["strengths"]
            or not result["improvements"] or not result["tips"]):
        raise ValueError(f"Coaching report did not parse into a complete result: {content[:200]!r}")

    return result

# Moved from ai_services.py: generate_practice_questions
def generate_practice_questions(job_description, resume=None):
    """Exactly 10 interview questions tailored to a job description (and,
    when provided, a candidate's resume) for the resume job-match page's
    video scan - shown after a scan completes so the candidate has
    something concrete to practice next, not a generic question bank."""
    resume_block = (
        f"\nCandidate's resume - tailor several questions to probe specific "
        f"experience it lists (depth, not just restating it):\n{resume[:2000]}\n"
    ) if resume else ""

    prompt = f"""Draft exactly 10 interview questions for this role, the kind a candidate should practice answering before a real interview.

Job Description: {(job_description or '')[:2000]}
{resume_block}
Cover a mix: a few background/motivation questions, several hands-on experience questions tied to specifics in the job description{" and the candidate's resume" if resume else ""}, at least one behavioral/situational question, and at least one question probing a likely weak spot relative to the role's requirements.

Respond with ONLY the 10 questions, one per line, no numbering, no extra commentary."""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.7,
    )
    lines = response.choices[0].message.content.strip().split("\n")
    questions = [line.strip().lstrip("-•0123456789. ").strip() for line in lines if line.strip()]
    return questions[:10]

# Moved from ai_services.py: generate_job_fit_verdict
def generate_job_fit_verdict(transcript, job_description):
    """One-shot assessment of whether what a candidate actually SAID in an
    interview answer demonstrates fit for a job description - distinct from
    generate_interview_coaching's communication-style score, this judges the
    content/substance against the role's requirements, not how well they
    spoke. Returns {"verdict": one of JOB_FIT_VERDICTS, "reasoning": str,
    "missed_requirements": list[str]} - missed_requirements names specific
    things the job description asks for that the answer never addressed at
    all (as opposed to reasoning, which explains the overall verdict).
    Raises ValueError if the model's output doesn't parse - same
    treat-as-unavailable contract as generate_interview_coaching."""
    prompt = f"""You are assessing whether a candidate's interview answer demonstrates they'd be a good fit for this specific job, based only on what they actually said - not how well or confidently they said it. This assessment is shown directly to the candidate themselves - address THEM as "you"/"your" throughout, never in the third person as "the candidate" or "they".

Job Description:
{(job_description or '')[:2000]}

Candidate's interview answer(s):
{transcript[:3000]}

Judge strictly: does the SUBSTANCE of what you said show relevant experience, skills, or understanding that matches this job's requirements? A well-spoken but generic or irrelevant answer should NOT score well here. A specific, relevant answer that directly addresses the role should score well even if communication style is plain.

Also identify specific requirements, skills, or responsibilities named in the job description that this answer never addressed at all - not weaknesses in how you answered, but concrete things the JD asks for that simply never came up. List 1-3; if the answer genuinely covers everything the JD calls for, say so with zero items rather than inventing gaps.

Respond EXACTLY in this format, no extra commentary:
Verdict: <Strong Yes|Yes|No|Strong No>
Reasoning: <3-5 sentences, addressed to "you", going into specific detail - what in your answer worked for this role, what specifically fell short, and why, citing concrete phrases from both the job description and what you said>
Missed: <a specific JD requirement/skill never addressed, or omit this line entirely if there are none>
Missed: <another, if applicable>"""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=450,
        temperature=0.2,
    )
    content = response.choices[0].message.content.strip()

    verdict, reasoning = None, None
    missed_requirements = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Verdict:"):
            candidate = line[8:].strip()
            if candidate in JOB_FIT_VERDICTS:
                verdict = candidate
        elif line.startswith("Reasoning:"):
            reasoning = line[10:].strip()
        elif line.startswith("Missed:"):
            item = line[7:].strip()
            if item:
                missed_requirements.append(item)

    if not verdict or not reasoning:
        raise ValueError(f"Job fit verdict did not parse into a complete result: {content[:200]!r}")

    return {"verdict": verdict, "reasoning": reasoning, "missed_requirements": missed_requirements}

# Moved from ai_services.py: generate_skills_roadmap
def generate_skills_roadmap(job_title, match_explanation, match_score, requirements):
    """Generate a specific 30-day action plan to close the skills gap for a role.
    Returns a list of {step, description, timeline} dicts."""
    prompt = f"""A candidate applied for {job_title} and scored {match_score}/100. Generate a specific, actionable 30-day plan to help them become competitive for this type of role.

Their match analysis:
{(match_explanation or '')[:800]}

Job requirements:
{(requirements or '')[:500]}

Create 4–5 specific steps. Each step must be concrete (name a specific skill, course type, or project to build — not just "learn Python"). Focus only on closing the actual gaps identified above.

Respond EXACTLY in this format:
Step: <short title (3-6 words)>
Description: <1-2 sentences — what exactly to do and why it closes a gap>
Timeline: <e.g. "Week 1–2" or "Days 1–7">

Step: ...
Description: ...
Timeline: ..."""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.3,
    )
    content = response.choices[0].message.content.strip()

    steps = []
    current = {}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Step:"):
            if current.get("step"):
                steps.append(current)
            current = {"step": line[5:].strip(), "description": "", "timeline": ""}
        elif line.startswith("Description:"):
            current["description"] = line[12:].strip()
        elif line.startswith("Timeline:"):
            current["timeline"] = line[9:].strip()
    if current.get("step"):
        steps.append(current)
    return steps[:5]

# Moved from ai_services.py: run_interview_turn
def run_interview_turn(role, job_description, user_message, history, force_conclude=False,
                        interview_length="standard", interview_focus=None, interview_questions=None,
                        practice_mode=False):
    """One turn of the AI recruiter-screen interview. The model alone decides
    when it has enough signal to stop asking questions and issue a verdict —
    no fixed question cap, just a length steer (short/standard/thorough) the
    employer chose for this job. force_conclude is only set by an explicit
    candidate "wrap up" action. Returns the assistant's reply text; the caller
    detects conclusion by checking whether the reply contains a "Verdict:"
    line, not by a precomputed flag.

    practice_mode=True is used for the candidate-facing practice interview
    (no real employer questions passed in, nothing saved or scored for real).
    It steers toward more concrete, role-specific questions grounded in the
    actual job description instead of generic templates like "tell me about
    a time..." with no connection to the role, since the whole point of
    practice is rehearsing for what this specific interview will look like."""
    context_block = f"\n=== ROLE ===\n{role}\n"
    if job_description:
        context_block += f"\n=== JOB DESCRIPTION ===\n{job_description[:2000]}\n"
    if interview_focus:
        context_block += (
            "\n=== EMPLOYER'S GUIDANCE FOR THIS INTERVIEW (topics to make sure get covered, things to "
            "listen for, and any conditional instructions — e.g. 'if a candidate mentions X, dig into Y' — "
            f"follow these as written) ===\n{interview_focus[:2000]}\n"
        )
    if interview_questions:
        questions_block = "\n".join(f"- {q}" for q in interview_questions[:15])
        context_block += (
            "\n=== EMPLOYER-WRITTEN QUESTIONS (work these in verbatim or near-verbatim over "
            f"the course of the interview) ===\n{questions_block}\n"
        )

    length_guidance = INTERVIEW_LENGTH_GUIDANCE.get(interview_length, INTERVIEW_LENGTH_GUIDANCE["standard"])

    if force_conclude:
        decision_rule = (
            "- The candidate has asked to wrap up. Do NOT ask another question. "
            f"Output a final verdict in EXACTLY this format:\n\n{VERDICT_FORMAT}\n\n"
            f"How to decide the verdict itself:\n{VERDICT_CRITERIA}"
        )
    else:
        decision_rule = (
            f"- YOU alone decide when you have enough signal to evaluate the candidate. {length_guidance}\n"
            f"- Once you have enough signal, end the interview by outputting a final verdict in EXACTLY this format instead of another question:\n\n{VERDICT_FORMAT}\n\n"
            f"How to decide the verdict itself:\n{VERDICT_CRITERIA}\n\n"
            "- Otherwise, continue with exactly one focused follow-up question, following the structure above."
        )

    practice_note = (
        "\nThis is a PRACTICE run - the candidate is rehearsing before their real interview, nothing here is "
        "saved or scored for a real hiring decision. Still run it like a real screen, but make every question "
        "concrete and specific to THIS job description (name the actual tools, responsibilities, or requirements "
        "it mentions) rather than a generic template question that could apply to any role. A candidate "
        "practicing should walk away knowing what this specific interview will actually probe.\n"
    ) if practice_mode else ""

    system_prompt = (
        "You are an experienced recruiter/hiring manager conducting a real screening interview for this "
        "specific role — not an interrogation, but a focused professional conversation. You ask ONE question "
        "at a time, push for concrete specifics and numbers instead of vague claims, and redirect rambling "
        "with a direct follow-up.\n"
        f"{practice_note}"
        f"{context_block}\n"
        "Structure the interview the way a real recruiter screen actually runs:\n"
        "1. Open with a quick question on background/motivation for this specific role.\n"
        "2. Spend 2-3 questions probing concrete hands-on experience and a specific project/result tied to the role.\n"
        "3. Ask one behavioral/situational question (e.g. handling a conflict, a failure, a tight deadline).\n"
        "4. Probe one likely weak spot relative to the role's requirements.\n"
        "5. If the employer left guidance above, follow it exactly — cover any topics it names, listen for "
        "what it says to listen for, and act on any conditional instructions the moment they apply (e.g. if "
        "it says to dig deeper when a candidate mentions something specific, do that the instant they do).\n"
        "6. If the employer wrote specific questions above, work every one of them into the conversation "
        "(verbatim or lightly reworded to fit the flow) in addition to the structure above.\n\n"
        "Guidelines:\n"
        "- Ask exactly one question per turn. No preamble, no encouragement, no filler.\n"
        "- If the candidate's answer is vague, demand a specific number, example, or outcome before moving on.\n"
        f"{decision_rule}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-20:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    if user_message:
        messages.append({"role": "user", "content": user_message})
    elif not history:
        messages.append({"role": "user", "content": "Begin the interview."})

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=messages,
        max_tokens=400,
        temperature=0.6,
    )
    return response.choices[0].message.content.strip()

# Moved from ai_services.py: generate_interview_question_preview
def generate_interview_question_preview(title, description, interview_length="standard", interview_focus=None):
    """Generates a full starting question bank for an employer to review and
    edit while setting up a job posting. The employer can edit, remove, or
    add to this list — whatever they keep gets worked into the real AI
    interview (see run_interview_turn's interview_questions param), so this
    is no longer purely illustrative. Returns a list of question strings."""
    length_guidance = INTERVIEW_LENGTH_GUIDANCE.get(interview_length, INTERVIEW_LENGTH_GUIDANCE["standard"])
    target_count = QUESTION_BANK_SIZE.get(interview_length, QUESTION_BANK_SIZE["standard"])
    focus_block = f"\nThe employer's guidance for this interview: {interview_focus[:2000]}\n" if interview_focus else ""

    prompt = f"""
You are drafting a full bank of recruiter-screen interview questions for this role. The employer will review
this list and can edit, remove, or add questions — whatever they keep will actually be asked of every
candidate, so make each question concrete and worth asking, not filler.

Role: {title}
Job Description: {description[:2000]}
{focus_block}
Length guidance: {length_guidance}

List {target_count} questions covering: background/motivation, several hands-on experience questions tied
to specifics in the job description, behavioral/situational questions, and weak-spot probes relative to the
role's requirements{"" if not interview_focus else ", plus at least one question per employer-requested focus area"}.

Respond with ONLY the questions, one per line, no numbering, no extra commentary.
"""
    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.7,
    )
    lines = response.choices[0].message.content.strip().split("\n")
    return [line.strip().lstrip("-•0123456789. ").strip() for line in lines if line.strip()]

