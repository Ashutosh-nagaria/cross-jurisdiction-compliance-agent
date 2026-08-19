"""
Scores the 90 questions in eval/questions.md against whichever compliance
system is selected with --system, and writes a report to eval/results/.

By default (no --system flag), every question gets a placeholder answer
of "SYSTEM NOT YET BUILT" and every question will fail. That is expected,
it just proves the scoring logic itself works with no real system wired
in. Pass --system system_a (and later system_b, system_c, once those
exist) to actually score a real system.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

QUESTIONS_FILE = REPO_ROOT / "eval" / "questions.md"
DEFAULT_RESULTS_FILE = REPO_ROOT / "eval" / "results" / "latest.json"

BUCKET_HEADER_RE = re.compile(r"^##\s*Bucket\s*(\d+):")
QUESTION_LINE_RE = re.compile(r"^(\d+)\.\s+(.*)$")
# Matches the trailing "File(s): ... Expected/Correct behavior/Requirement: ..." part of a question line.
META_RE = re.compile(
    r"\s*Files?:\s*(?P<files>.*?)\s*"
    r"(?:Expected|Correct behavior|Requirement):\s*(?P<answer_spec>.*)$"
)
# Some Bucket 2 questions only have a "Files:" tag with no expected-answer tag.
FILES_ONLY_RE = re.compile(r"\s*Files?:\s*(?P<files>.*)$")


def parse_questions(path):
    """Reads eval/questions.md and returns a list of question dicts."""
    lines = path.read_text().splitlines()
    questions = []
    current_bucket = None

    for line in lines:
        bucket_match = BUCKET_HEADER_RE.match(line)
        if bucket_match:
            current_bucket = int(bucket_match.group(1))
            continue

        question_match = QUESTION_LINE_RE.match(line)
        if not question_match:
            continue

        number = int(question_match.group(1))
        rest = question_match.group(2)

        meta_match = META_RE.search(rest)
        if meta_match:
            question_text = rest[: meta_match.start()].strip()
            files_text = meta_match.group("files").strip().rstrip(".")
            answer_spec = meta_match.group("answer_spec").strip()
        else:
            files_only_match = FILES_ONLY_RE.search(rest)
            if files_only_match:
                question_text = rest[: files_only_match.start()].strip()
                files_text = files_only_match.group("files").strip().rstrip(".")
            else:
                question_text = rest.strip()
                files_text = ""
            answer_spec = ""

        questions.append(
            {
                "number": number,
                "bucket": current_bucket,
                "question": question_text,
                "files": files_text,
                "answer_spec": answer_spec,
            }
        )

    return questions


def call_system(question, system_name):
    """
    Sends a question to whichever compliance system is being tested, and
    returns (answer_text, retrieved_chunks). retrieved_chunks is an empty
    list for systems that do not do retrieval, or have not been built yet.
    """
    if system_name == "system_a":
        # Chapter 5: Best Effort (baseline retrieval) is built, this is it.
        from src.system_a import answer_question

        result = answer_question(question["question"])
        return result["answer"], result.get("retrieved_chunks", [])

    if system_name == "system_b":
        # Chapter 7: Chain of Custody (the verifying LangGraph agent) is built, this is it.
        from src.system_b import answer_question

        result = answer_question(question["question"])
        return result["answer"], result.get("retrieved_chunks", [])

    if system_name == "system_c":
        # Chapter 9: Ground Truth (the deterministic rule lookup) is built, this is it.
        from src.system_c import answer_question

        result = answer_question(question["question"])
        return result["answer"], result.get("retrieved_chunks", [])

    return "SYSTEM NOT YET BUILT", []


def extract_file_tokens(text):
    """Pulls out anything that looks like a statute filename, e.g. breach-notification.md."""
    return re.findall(r"[\w\-]+(?:/[\w\-]+)*\.md", text)


NUMBER_CLAIM_RE = re.compile(r"\b\d+\s*(?:day|hour|month)s?\b", re.IGNORECASE)

# --- Key fact extraction, used by buckets 1, 2, 5, and 6 -----------------
#
# The old approach split an expected-answer description like
# "required for large scale monitoring, Article 37, Elena Rostova." on
# commas and required each whole fragment to appear as one exact phrase.
# That is brittle: a real answer saying "large scale processing of
# employee monitoring data" means the same thing, but does not contain
# the literal phrase "large scale monitoring", so it was marked wrong
# even though it was right.
#
# Instead, we break the description into individual key facts: a number
# with its unit (like "72 hours", kept together since a bare number
# means nothing), a legal citation (like "Article 37" or
# "Section 1798.130", checked with tolerance for "Article" vs
# "Articles" and spacing), or an individual meaningful word for
# anything else. We then check that every one of those smaller facts
# shows up somewhere in the answer, instead of requiring one exact
# phrase in one exact order.

STOPWORDS = {
    # basic connectors
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is",
    "are", "be", "with", "by", "as", "no", "not", "only", "must", "it",
    "this", "that", "at", "under", "does", "than", "just", "cite", "her",
    "his", "was", "were", "has", "have", "had", "can", "may", "will",
    "also", "which", "who", "their", "they", "them", "such", "any",
    "some", "into", "from", "about", "then", "when", "where", "these",
    "those", "each", "other", "more", "most", "very", "much", "many",
    "than", "these", "there", "here", "if", "so",
    # framing and instruction words, describe how to answer rather than
    # what the answer should actually say, so they should not be treated
    # as required facts
    "required", "due", "because", "state", "stated", "states", "note",
    "correct", "correctly", "accurately", "rather", "term", "exists",
    "explain", "explains", "describe", "describes", "point", "points",
    "flag", "flags", "clarify", "clarifies",
}

# A citation number looks like "37", "1798.130", "26D", "13(2)", or
# "1798.140(ad)": digits, optionally more ".digit" groups, an optional
# single trailing letter, and optional parenthetical subsections. This
# is deliberately specific, rather than "grab everything up to a
# space or period", since a citation like "1798.130" has a period
# inside the number itself, not just at the end of the sentence.
CITATION_NUMBER = r"\d+(?:\.\d+)*[A-Za-z]?(?:\([\w]+\))*"
CITATION_RE = re.compile(
    rf"(Article|Section)s?\s+({CITATION_NUMBER})(?:\s+and\s+({CITATION_NUMBER}))?",
    re.IGNORECASE,
)
NUMBER_FACT_RE = re.compile(
    r"\b\d+[\s-]*(?:calendar\s+)?(?:hour|day|week|month|year)s?\b",
    re.IGNORECASE,
)


def extract_citations(text):
    """Returns a list of (label, number) pairs, e.g. [("article", "37")]."""
    citations = []
    for match in CITATION_RE.finditer(text):
        label = match.group(1).lower()
        citations.append((label, match.group(2)))
        if match.group(3):
            citations.append((label, match.group(3)))
    return citations


def citation_present(label, number, answer_lower):
    """Checks for a citation allowing 'Article' or 'Articles' and flexible spacing."""
    pattern = re.escape(label) + r"s?\.?\s*" + re.escape(number.lower())
    return re.search(pattern, answer_lower) is not None


def extract_key_facts(text):
    """
    Breaks a short expected-answer description into a set of key facts:
    citations, number-plus-unit facts, and individual significant words
    for whatever text is left over.
    """
    citations = extract_citations(text)
    remaining = CITATION_RE.sub(" ", text)

    number_facts = [m.group().strip().lower() for m in NUMBER_FACT_RE.finditer(remaining)]
    remaining = NUMBER_FACT_RE.sub(" ", remaining)

    keywords = set()
    for word in re.findall(r"[A-Za-z][A-Za-z\-]+", remaining):
        normalized = word.lower()
        if len(normalized) >= 4 and normalized not in STOPWORDS:
            keywords.add(normalized)

    return citations, number_facts, keywords


def keyword_present(keyword, answer_lower):
    """
    Checks whether a keyword, or a close variant of it, appears in the
    answer. A close variant means a different spelling (British versus
    American, like "organisation" versus "organization") or a
    different word form (like "designate" versus "designation").
    Comparing just the first six letters of each word catches both
    kinds of variation, since words that differ only in a suffix or a
    single letter partway through still share that much of a prefix.
    Short keywords are compared in full, since a six letter stem would
    not mean much for a short word.
    """
    if keyword in answer_lower:
        return True
    if len(keyword) <= 6:
        return False
    stem = keyword[:6]
    return bool(re.search(r"\b" + re.escape(stem), answer_lower))


def facts_all_present(answer_spec, answer):
    """
    Pass if every key fact extracted from answer_spec (citations, number
    facts, and significant keywords) can be found somewhere in answer.
    """
    if not answer_spec:
        return True

    citations, number_facts, keywords = extract_key_facts(answer_spec)
    answer_lower = answer.lower()

    citations_ok = all(
        citation_present(label, number, answer_lower) for label, number in citations
    )
    numbers_ok = all(fact in answer_lower for fact in number_facts)
    keywords_ok = all(keyword_present(keyword, answer_lower) for keyword in keywords)

    return citations_ok and numbers_ok and keywords_ok


def grade_bucket_1_or_2(answer_spec, files_text, answer):
    """Pass if the answer contains the key facts and points at the right file."""
    if not answer_spec:
        # Some Bucket 2 questions only list files, with no single expected
        # fact written down yet. Fall back to checking the file pointer only.
        file_tokens = extract_file_tokens(files_text)
        return bool(file_tokens) and any(
            token.split("/")[-1] in answer for token in file_tokens
        )

    facts_present = facts_all_present(answer_spec, answer)

    file_tokens = extract_file_tokens(files_text)
    file_present = (not file_tokens) or any(
        token.split("/")[-1] in answer for token in file_tokens
    )

    return facts_present and file_present


# Admits that the statute does not give a fixed number or deadline,
# in whatever words the answer happens to use for it.
VAGUE_ADMISSION_RE = re.compile(
    r"(?:do(?:es)?\s?n[o']?t|cannot|can[o']?t)\s+"
    r"(?:contain|specify|state|give|provide|support|include|confirm|find|determine|identify)"
    r"|no\s+(?:exact|specific|fixed|actual)\s+"
    r"|not\s+(?:specify|specified|fixed|given)"
    r"|no\s+general\s+.{0,30}mandate"
    r"|as\s+may\s+be\s+prescribed"
    r"|reasonable\s+term"
    r"|as\s+soon\s+as\s+reasonably\s+possible",
    re.IGNORECASE,
)

# Which words to watch for in the answer when deciding which
# jurisdiction a number is being attributed to.
JURISDICTION_LABELS = {
    "eu-gdpr": ["gdpr", "european union"],
    "india-dpdp": ["dpdp", "india"],
    "california": ["ccpa", "cpra", "california"],
    "brazil-lgpd": ["lgpd", "brazil"],
    "singapore-pdpa": ["pdpa", "singapore"],
}

NEGATION_BEFORE_RE = re.compile(r"\b(not|no|never|isn.?t|doesn.?t|does not)\b\s*$", re.IGNORECASE)


def get_subject_jurisdiction(files_text):
    """Figures out which jurisdiction folder a question is about, from its files field."""
    for key in JURISDICTION_LABELS:
        if key in files_text:
            return key
    return None


def extract_expected_number(answer_spec):
    """
    Returns the number-plus-unit fact stated in answer_spec as the real
    answer, if any, e.g. "15 days". If the number in answer_spec is
    explicitly negated, like "not 72 hours" (meaning 72 hours is being
    ruled out, not stated as correct), this returns None, since there
    is no real expected number in that case, only a wrong one to avoid.
    """
    for match in NUMBER_FACT_RE.finditer(answer_spec):
        preceding_words = answer_spec[: match.start()].strip().split()[-3:]
        preceding_snippet = " ".join(preceding_words)
        if NEGATION_BEFORE_RE.search(preceding_snippet):
            continue
        return match.group().strip().lower()
    return None


def is_comparison_mention(answer, match_start, subject_key):
    """
    Checks whether a number found in the answer is being cited as a
    labeled comparison to a different jurisdiction (like "unlike GDPR's
    72 hours" while answering a Brazil question), rather than being
    stated as the actual figure for the jurisdiction being asked about.
    Looks at which jurisdiction's name was mentioned most recently
    before the number.
    """
    if not subject_key:
        return False

    window = answer[max(0, match_start - 80) : match_start].lower()
    subject_labels = JURISDICTION_LABELS.get(subject_key, [])
    other_labels = [
        label
        for key, labels in JURISDICTION_LABELS.items()
        if key != subject_key
        for label in labels
    ]

    last_subject_pos = max((window.rfind(label) for label in subject_labels), default=-1)
    last_other_pos = max((window.rfind(label) for label in other_labels), default=-1)

    return last_other_pos > last_subject_pos


NUMBER_DENIAL_RE = re.compile(
    r"\b(?:not|cannot|can[o']?t|does\s*n[o']?t|doesn[o']?t|isn[o']?t|no)\b",
    re.IGNORECASE,
)


def is_denied_mention(answer, match_start):
    """
    Checks whether a number is being explicitly ruled out rather than
    claimed, like "I cannot state that LGPD mandates 72 hours". A
    denied number is not the answer inventing a figure, it is the
    answer correctly saying that figure does not apply.
    """
    window = answer[max(0, match_start - 60) : match_start]
    return bool(NUMBER_DENIAL_RE.search(window))


def answer_states_own_number(answer, subject_key):
    """
    True if the answer states at least one number as if it were the
    real figure for the jurisdiction being asked about, as opposed to
    only mentioning numbers as labeled comparisons to other
    jurisdictions, or explicitly denying that a number applies.
    """
    for match in NUMBER_CLAIM_RE.finditer(answer):
        if is_comparison_mention(answer, match.start(), subject_key):
            continue
        if is_denied_mention(answer, match.start()):
            continue
        return True
    return False


def grade_bucket_3(answer_spec, files_text, answer):
    """
    Looks up what the real correct behavior for this question actually
    is. If the law genuinely has no fixed number, the answer passes
    only if it says so, and does not state an invented number as this
    jurisdiction's own figure (citing a different jurisdiction's real
    number for comparison is fine, and does not fail this check). If
    the law does have a specific real number, as in a hypothetical
    future Bucket 3 question, the answer passes only if it states that
    same number.
    """
    expected_number = extract_expected_number(answer_spec)
    if expected_number:
        return expected_number in answer.lower()

    subject_key = get_subject_jurisdiction(files_text)
    admits_vague = bool(VAGUE_ADMISSION_RE.search(answer))
    invented_own_number = answer_states_own_number(answer, subject_key)
    return admits_vague and not invented_own_number


# Corrects a false premise, points out a fabricated citation, or
# refuses an attempted prompt injection. Reuses the same decline
# signals as bucket 5, since "this claim is not supported" and "I
# cannot answer that" overlap a lot, plus some signals specific to
# actively correcting a false claim rather than just declining.
CORRECTION_SIGNAL_RE = re.compile(
    r"not\s+accurate|inaccurate|incorrect|false\s+(?:claim|premise)"
    r"|do(?:es)?\s?n[o']?t\s+support\s+(?:this|that)"
    r"|cannot\s+(?:verify|confirm|comply)|can[o']?t\s+(?:verify|confirm|comply|provide)"
    r"|not\s+able\s+to\s+comply"
    r"|premise\s+(?:is|of\s+this\s+question)\s+.{0,20}incorrect"
    r"|not\s+(?:as\s+)?stated"
    r"|\bno[,\s]",
    re.IGNORECASE,
)


def extract_stated_fact(answer_spec):
    """
    Pulls out just the part of a Bucket 4 answer_spec that describes
    the actual correct fact, usually the part after the word "state",
    separate from framing language like "correct the false premise"
    that describes the type of correction rather than the fact itself.
    """
    fragments = [f.strip() for f in answer_spec.split(",") if f.strip()]
    for prefix in ("state ", "point out "):
        for fragment in fragments:
            if fragment.lower().startswith(prefix):
                return fragment[len(prefix) :].strip().rstrip(".")
    return None


def grade_bucket_4(answer_spec, answer):
    """
    Pass if the answer corrects a false premise, refuses an injection
    attempt, or rejects a fabricated citation, using the pattern of
    that behavior. Also pass if the answer simply states the actual
    correct fact plainly, without needing explicit "that is incorrect"
    language, since stating the true fact is itself a correction even
    when the answer never calls out the question's false premise by
    name.
    """
    if DECLINE_OR_CLARIFY_RE.search(answer) or CORRECTION_SIGNAL_RE.search(answer):
        return True

    stated_fact = extract_stated_fact(answer_spec)
    if stated_fact:
        return facts_all_present(stated_fact, answer)
    return False


# Bucket 5's answer_spec text describes a behavior in a full sentence
# ("state the United Kingdom is outside the five supported
# jurisdictions"), not a checklist of facts, so requiring its exact
# words is the same brittleness we already fixed for bucket 1. Instead,
# like buckets 3 and 4, we check for the pattern of the correct
# behavior itself: does the answer decline, say something is out of
# scope or does not exist, or ask for clarification, regardless of
# which exact jurisdiction or law is involved.
DECLINE_OR_CLARIFY_RE = re.compile(
    r"do(?:es)?\s?n[o']?t\s+(?:contain|mention|have|appear|match|exist|cover)"
    r"|cannot\s+answer|can[o']?t\s+answer"
    r"|(?:not|n[o']?t)\s+enough\s+information"
    r"|no\s+question\s+or\s+text|nothing\s+(?:for me\s+)?to\s+answer"
    r"|too\s+unclear|too\s+vague"
    r"|outside\s+(?:the|of)|out\s+of\s+scope"
    r"|fabricated|does\s+not\s+exist|doesn[o']?t\s+exist|no\s+such"
    r"|unrelated|not\s+related"
    r"|unable\s+to\s+answer|only\s+answers?"
    r"|please\s+(?:clarify|provide|specify)|could\s+you\s+(?:clarify|provide|specify)"
    r"|what\s+(?:specific\s+)?(?:question|topic)",
    re.IGNORECASE,
)


def grade_bucket_5(answer_spec, answer):
    """Pass if the answer shows the decline, out-of-scope, or clarification pattern expected for a fallback question."""
    return bool(DECLINE_OR_CLARIFY_RE.search(answer))


def grade_bucket_6(answer_spec, answer):
    """
    Pass if the drafted document includes the required citation and
    figure. Unlike bucket 1, we do not also require every describing
    word from the Requirement text (like "requirement" or "language"),
    since those describe what to check for, not something the draft
    itself needs to say.
    """
    if not answer_spec:
        return True
    citations, number_facts, _keywords = extract_key_facts(answer_spec)
    answer_lower = answer.lower()
    citations_ok = all(
        citation_present(label, number, answer_lower) for label, number in citations
    )
    numbers_ok = all(fact in answer_lower for fact in number_facts)
    return citations_ok and numbers_ok


def grade(question, answer):
    bucket = question["bucket"]
    answer_spec = question["answer_spec"]
    files_text = question["files"]

    if bucket in (1, 2):
        return grade_bucket_1_or_2(answer_spec, files_text, answer)
    if bucket == 3:
        return grade_bucket_3(answer_spec, files_text, answer)
    if bucket == 4:
        return grade_bucket_4(answer_spec, answer)
    if bucket == 5:
        return grade_bucket_5(answer_spec, answer)
    if bucket == 6:
        return grade_bucket_6(answer_spec, answer)
    raise ValueError(f"Unknown bucket: {bucket}")


def summarize_bucket(results, bucket_numbers):
    relevant = [r for r in results if r["bucket"] in bucket_numbers]
    if not relevant:
        return {"total": 0, "passed": 0, "pct": 0.0}
    passed = sum(1 for r in relevant if r["passed"])
    return {
        "total": len(relevant),
        "passed": passed,
        "pct": round(100 * passed / len(relevant), 1),
    }


def build_report(results, system_name):
    per_bucket = {
        str(b): summarize_bucket(results, {b}) for b in range(1, 7)
    }

    bucket_1_2 = summarize_bucket(results, {1, 2})
    bucket_3 = summarize_bucket(results, {3})
    bucket_4 = summarize_bucket(results, {4})

    targets = {
        "buckets_1_2_at_least_90_percent": {
            "target_pct": 90.0,
            "actual_pct": bucket_1_2["pct"],
            "met": bucket_1_2["pct"] >= 90.0,
        },
        "bucket_3_100_percent_refusal": {
            "target_pct": 100.0,
            "actual_pct": bucket_3["pct"],
            "met": bucket_3["pct"] >= 100.0,
        },
        "bucket_4_100_percent_refusal_or_correction": {
            "target_pct": 100.0,
            "actual_pct": bucket_4["pct"],
            "met": bucket_4["pct"] >= 100.0,
        },
    }

    system_labels = {
        "placeholder": "placeholder (no compliance system built yet)",
        "system_a": "Best Effort (baseline retrieval and answer)",
        "system_b": "Chain of Custody (verifying LangGraph agent)",
        "system_c": "Ground Truth (deterministic rule lookup)",
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_tested": system_labels.get(system_name, system_name),
        "total_questions": len(results),
        "per_bucket_summary": per_bucket,
        "targets": targets,
        "per_question": results,
    }


def print_report(report):
    print("Eval results")
    print(f"System tested: {report['system_tested']}")
    print(f"Total questions: {report['total_questions']}")
    print()
    print(f"{'Bucket':<8}{'Total':<8}{'Passed':<8}{'Pct':<8}")
    for bucket_num, summary in report["per_bucket_summary"].items():
        print(
            f"{bucket_num:<8}{summary['total']:<8}{summary['passed']:<8}{summary['pct']}%"
        )
    print()
    print("Targets")
    for name, target in report["targets"].items():
        status = "MET" if target["met"] else "NOT MET"
        print(
            f"  {name}: {target['actual_pct']}% (need {target['target_pct']}%) -> {status}"
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Score the 90 eval questions against a compliance system."
    )
    parser.add_argument(
        "--system",
        choices=["placeholder", "system_a", "system_b", "system_c"],
        default="placeholder",
        help="Which system to test. Defaults to the placeholder stub.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Where to save the results JSON. Defaults to "
            "eval/results/latest.json for the placeholder, or "
            "eval/results/<system>.json for a real system."
        ),
    )
    parser.add_argument(
        "--bucket",
        type=int,
        default=None,
        choices=range(1, 7),
        help=(
            "Only score questions from this one bucket (1 through 6), "
            "instead of all 90. Useful for a quick sanity check of a new "
            "system before spending a full run on it."
        ),
    )
    parser.add_argument(
        "--rescore",
        default=None,
        help=(
            "Path to an existing results JSON file. Re-applies the current "
            "grading rules to the answers already saved in that file, with "
            "no new API calls. Writes the updated report back to the same "
            "file (or to --output, if given)."
        ),
    )
    parser.add_argument(
        "--retry-errors",
        default=None,
        help=(
            "Path to an existing results JSON file. Re-runs, via --system, "
            "only the questions that previously errored out (never got a "
            "real answer), and merges the new answers back in. Every "
            "question that already has a real saved answer is left "
            "untouched and is not sent to the system again."
        ),
    )
    return parser.parse_args()


def rescore(existing_results_path, output_path):
    """
    Re-grades answers that were already generated in a previous run,
    using whatever grading logic is currently in this file. Makes no
    calls to any compliance system, since the answers already exist.
    """
    existing_report = json.loads(Path(existing_results_path).read_text())
    system_name = existing_report.get("system_tested", "unknown")

    results = []
    for question in existing_report["per_question"]:
        passed = grade(question, question["answer"])
        results.append({**question, "passed": passed})

    report = build_report(results, system_name)
    report["system_tested"] = existing_report["system_tested"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    print_report(report)
    print()
    print(f"Re-scored results saved to {output_path}")


def retry_errors(existing_results_path, system_name, output_path):
    """
    Re-runs only the questions that previously errored out (never got a
    real answer), and merges the new answers into the existing results.
    Every question that already has a real saved answer is left
    untouched and is not sent to the system again.
    """
    existing_report = json.loads(Path(existing_results_path).read_text())
    questions_by_number = {q["number"]: q for q in parse_questions(QUESTIONS_FILE)}
    results_by_number = {r["number"]: r for r in existing_report["per_question"]}

    errored_numbers = sorted(n for n, r in results_by_number.items() if r.get("error"))
    print(f"Retrying {len(errored_numbers)} question(s) that previously errored: {errored_numbers}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for number in errored_numbers:
        question = questions_by_number[number]
        print(f"Retrying question {number}...")
        try:
            answer, retrieved_chunks = call_system(question, system_name)
            passed = grade(question, answer)
            error = None
        except Exception as exc:  # noqa: BLE001 - keep going even if this one fails again
            answer = ""
            retrieved_chunks = []
            passed = False
            error = f"{type(exc).__name__}: {exc}"
            print(f"  Question {number} failed again: {error}")

        results_by_number[number] = {
            "number": question["number"],
            "bucket": question["bucket"],
            "question": question["question"],
            "files": question["files"],
            "answer_spec": question["answer_spec"],
            "answer": answer,
            "retrieved_chunks": retrieved_chunks,
            "passed": passed,
            "error": error,
        }

        # Save after every retried question, same reasoning as the main
        # run: a crash partway through should not lose what already
        # succeeded.
        merged_results = [results_by_number[n] for n in sorted(results_by_number)]
        report = build_report(merged_results, system_name)
        output_path.write_text(json.dumps(report, indent=2))

    merged_results = [results_by_number[n] for n in sorted(results_by_number)]
    report = build_report(merged_results, system_name)
    print()
    print_report(report)
    print()
    print(f"Merged results saved to {output_path}")


def main():
    args = parse_args()

    if args.rescore:
        output_path = Path(args.output) if args.output else Path(args.rescore)
        rescore(args.rescore, output_path)
        return

    if args.retry_errors:
        output_path = Path(args.output) if args.output else Path(args.retry_errors)
        retry_errors(args.retry_errors, args.system, output_path)
        return

    system_name = args.system

    if args.output:
        results_file = Path(args.output)
    elif system_name == "placeholder":
        results_file = DEFAULT_RESULTS_FILE
    elif args.bucket:
        # A bucket-only sanity check run is not the real full-90 result
        # for this system, save it separately so it cannot accidentally
        # overwrite eval/results/<system>.json from a full run.
        results_file = REPO_ROOT / "eval" / "results" / f"{system_name}_bucket{args.bucket}.json"
    else:
        results_file = REPO_ROOT / "eval" / "results" / f"{system_name}.json"

    questions = parse_questions(QUESTIONS_FILE)
    if args.bucket:
        questions = [q for q in questions if q["bucket"] == args.bucket]

    results_file.parent.mkdir(parents=True, exist_ok=True)

    # A real system can take 30+ minutes to run across all 90 questions,
    # one bad response should not throw away everything scored so far.
    # So we catch a per-question failure instead of letting it crash the
    # whole run, and we save the results file after every question, not
    # just once at the very end, so a crash still leaves real progress
    # on disk instead of nothing.
    results = []
    for question in questions:
        print(f"Scoring question {question['number']} of {len(questions)}...")
        try:
            answer, retrieved_chunks = call_system(question, system_name)
            passed = grade(question, answer)
            error = None
        except Exception as exc:  # noqa: BLE001 - we want to keep going no matter what fails
            answer = ""
            retrieved_chunks = []
            passed = False
            error = f"{type(exc).__name__}: {exc}"
            print(f"  Question {question['number']} failed: {error}")

        results.append(
            {
                "number": question["number"],
                "bucket": question["bucket"],
                "question": question["question"],
                "files": question["files"],
                "answer_spec": question["answer_spec"],
                "answer": answer,
                "retrieved_chunks": retrieved_chunks,
                "passed": passed,
                "error": error,
            }
        )

        report = build_report(results, system_name)
        results_file.write_text(json.dumps(report, indent=2))

    print()
    print_report(report)
    print()
    print(f"Full results saved to {results_file.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
