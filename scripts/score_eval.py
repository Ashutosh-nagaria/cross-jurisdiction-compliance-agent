"""
Scores the 90 questions in eval/questions.md against whichever compliance
system is plugged in below, and writes a report to eval/results/latest.json.

Right now, no compliance system has been built yet (that is Chapter 5
onward), so every question gets a placeholder answer of
"SYSTEM NOT YET BUILT" and every question will fail. That is expected.
Running this script today proves the scoring logic itself works. Once
System A, B, or C exist, this script will start producing a real score.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = REPO_ROOT / "eval" / "questions.md"
RESULTS_FILE = REPO_ROOT / "eval" / "results" / "latest.json"

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


def call_system(question):
    """
    Placeholder answer function. Every question gets the same stand-in
    text until a real compliance system exists.

    This is where the real systems get plugged in later, one at a time:

    # Chapter 5: once System A (baseline retrieval) exists, replace the
    # line below with something like:
    #     return system_a.answer(question["question"])

    # Chapter 7: once System B (the verifying agent) exists, add a
    # second call here (or a separate score_eval run) like:
    #     return system_b.answer(question["question"])

    # Chapter 9: once System C (the deterministic rule lookup) exists,
    # add a third call here (or a separate score_eval run) like:
    #     return system_c.answer(question["question"])
    """
    return "SYSTEM NOT YET BUILT"


def extract_file_tokens(text):
    """Pulls out anything that looks like a statute filename, e.g. breach-notification.md."""
    return re.findall(r"[\w\-]+(?:/[\w\-]+)*\.md", text)


NUMBER_CLAIM_RE = re.compile(r"\b\d+\s*(?:day|hour|month)s?\b", re.IGNORECASE)


def grade_bucket_1_or_2(answer_spec, files_text, answer):
    """Pass if the answer contains the key facts and points at the right file."""
    if not answer_spec:
        # Some Bucket 2 questions only list files, with no single expected
        # fact written down yet. Fall back to checking the file pointer only.
        file_tokens = extract_file_tokens(files_text)
        return bool(file_tokens) and any(
            token.split("/")[-1] in answer for token in file_tokens
        )

    fact_fragments = [f.strip() for f in answer_spec.split(",") if f.strip()]
    facts_present = all(fragment.lower() in answer.lower() for fragment in fact_fragments)

    file_tokens = extract_file_tokens(files_text)
    file_present = (not file_tokens) or any(
        token.split("/")[-1] in answer for token in file_tokens
    )

    return facts_present and file_present


def grade_bucket_3(answer_spec, answer):
    """Pass only if the answer admits there is no fixed number, and does not invent one."""
    vague_fragments = [f.strip() for f in answer_spec.split(",") if f.strip()]
    admits_vague = any(fragment.lower() in answer.lower() for fragment in vague_fragments)
    invented_a_number = bool(NUMBER_CLAIM_RE.search(answer))
    return admits_vague and not invented_a_number


def grade_bucket_4(answer_spec, answer):
    """Pass if the answer contains the correction described in answer_spec."""
    fragments = [f.strip() for f in answer_spec.split(",") if f.strip()]
    return any(fragment.lower() in answer.lower() for fragment in fragments)


def grade_bucket_5(answer_spec, answer):
    """Pass if the answer contains the scope refusal or clarification described in answer_spec."""
    fragments = [f.strip() for f in answer_spec.split(",") if f.strip()]
    return any(fragment.lower() in answer.lower() for fragment in fragments)


def grade_bucket_6(answer_spec, answer):
    """Pass if the drafted answer includes the required citation."""
    fragments = [f.strip() for f in answer_spec.split(",") if f.strip()]
    return all(fragment.lower() in answer.lower() for fragment in fragments)


def grade(question, answer):
    bucket = question["bucket"]
    answer_spec = question["answer_spec"]
    files_text = question["files"]

    if bucket in (1, 2):
        return grade_bucket_1_or_2(answer_spec, files_text, answer)
    if bucket == 3:
        return grade_bucket_3(answer_spec, answer)
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


def build_report(results):
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

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_tested": "placeholder (no compliance system built yet)",
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


def main():
    questions = parse_questions(QUESTIONS_FILE)

    results = []
    for question in questions:
        answer = call_system(question)
        passed = grade(question, answer)
        results.append(
            {
                "number": question["number"],
                "bucket": question["bucket"],
                "question": question["question"],
                "files": question["files"],
                "answer_spec": question["answer_spec"],
                "answer": answer,
                "passed": passed,
            }
        )

    report = build_report(results)

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(report, indent=2))

    print_report(report)
    print()
    print(f"Full results saved to {RESULTS_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
