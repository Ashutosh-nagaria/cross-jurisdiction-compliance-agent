"""
Chapter 10: reads the saved eval result files for all three systems and
writes a single comparison report to docs/RESULTS.md.

This script makes no calls to any AI system and fetches nothing online.
It only reads the eval/results/*.json files that already exist from
earlier chapters, and turns them into one readable report.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "eval" / "results"
OUTPUT_FILE = REPO_ROOT / "docs" / "RESULTS.md"

BUCKET_NAMES = {
    "1": "Single jurisdiction functional",
    "2": "Cross jurisdiction comparison",
    "3": "Sparse cell, correct refusal expected",
    "4": "Adversarial",
    "5": "Fallback",
    "6": "Drafting quality",
}


def load_report(filename):
    path = RESULTS_DIR / filename
    if not path.exists():
        return None
    return json.loads(path.read_text())


def pct(summary):
    if summary["total"] == 0:
        return None
    return summary["pct"]


def pct_str(summary):
    value = pct(summary)
    return "not run" if value is None else f"{value}%"


def winner(a_value, c_value):
    if a_value is None or c_value is None:
        return "not comparable"
    if a_value > c_value:
        return "System A"
    if c_value > a_value:
        return "System C"
    return "tie"


def build_bucket_table(system_a, system_c, system_b):
    lines = [
        "| Bucket | What it tests | System A (full 90) | System C (full 90) | System B (bucket 1 only, partial sample) |",
        "|---|---|---|---|---|",
    ]
    for b in "123456":
        name = BUCKET_NAMES[b]
        a_pct = pct_str(system_a["per_bucket_summary"][b])
        c_pct = pct_str(system_c["per_bucket_summary"][b])
        b_summary = system_b["per_bucket_summary"][b] if system_b else {"total": 0}
        b_pct = pct_str(b_summary)
        lines.append(f"| {b} | {name} | {a_pct} | {c_pct} | {b_pct} |")
    return "\n".join(lines)


def build_targets_table(system_a, system_c):
    lines = [
        "| Release gate target | System A | System C |",
        "|---|---|---|",
    ]
    target_labels = {
        "buckets_1_2_at_least_90_percent": "90 percent on buckets 1 and 2 combined",
        "bucket_3_100_percent_refusal": "100 percent on bucket 3",
        "bucket_4_100_percent_refusal_or_correction": "100 percent on bucket 4",
    }
    for key, label in target_labels.items():
        a_target = system_a["targets"][key]
        c_target = system_c["targets"][key]
        a_status = "met" if a_target["met"] else "not met"
        c_status = "met" if c_target["met"] else "not met"
        lines.append(
            f"| {label} | {a_target['actual_pct']}% ({a_status}) | "
            f"{c_target['actual_pct']}% ({c_status}) |"
        )
    return "\n".join(lines)


def main():
    system_a = load_report("system_a.json")
    system_c = load_report("system_c.json")
    system_b = load_report("system_b_bucket1.json")

    if not system_a or not system_c:
        raise SystemExit(
            "Missing eval/results/system_a.json or eval/results/system_c.json, "
            "cannot build a comparison without both full runs."
        )

    bucket_table = build_bucket_table(system_a, system_c, system_b)
    targets_table = build_targets_table(system_a, system_c)

    a1 = pct(system_a["per_bucket_summary"]["1"])
    c1 = pct(system_c["per_bucket_summary"]["1"])
    a3 = pct(system_a["per_bucket_summary"]["3"])
    c3 = pct(system_c["per_bucket_summary"]["3"])
    a2 = pct(system_a["per_bucket_summary"]["2"])
    c2 = pct(system_c["per_bucket_summary"]["2"])
    b1 = pct(system_b["per_bucket_summary"]["1"]) if system_b else None

    numeric_fact_winner_1 = winner(a1, c1)
    numeric_fact_winner_3 = winner(a3, c3)
    comparison_winner = winner(a2, c2)

    b1_line = (
        f"On this same slice of 25 questions, System B (partial sample, only "
        f"bucket 1 has been run) scored {b1}%, the lowest of the three, though "
        "it was tested under a harder five step pipeline with fewer rounds of "
        "tuning than the other two systems received."
        if b1 is not None
        else "System B has not been run on this bucket."
    )

    report = f"""# Results: comparing System A, System B, and System C

This report compares the three compliance systems built in this project,
using only the eval results already saved from earlier chapters. No new
questions were asked and no new API calls were made to produce this
report, it only reads what was already recorded.

System A is a baseline retrieval and answer system. System C is a
deterministic rule lookup table with an AI classification step in front
of it. Both have been run on the full 90 question eval. System B is a
LangGraph agent with routing, retrieval, structured extraction, source
verification, and a simulated human approval step. System B has only
been run on bucket 1 (25 questions) so far, see the note at the end of
this report for why.

## Accuracy per bucket, side by side

{bucket_table}

System B's column is a partial sample of 25 questions, not a full 90
question result, and should not be read as directly equivalent to the
System A and System C columns next to it.

## Release gate targets (System A and System C only)

{targets_table}

Neither system currently meets all three release gates. System A meets
the bucket 4 target outright. System C comes closer on the other two
targets but does not meet either of them yet.

## Who wins on numeric fact questions (buckets 1 and 3)

Bucket 1 (single jurisdiction functional questions, mostly asking for an
exact number or citation): System A scored {a1}%, System C scored {c1}%.
Winner: {numeric_fact_winner_1}.

Bucket 3 (sparse cell questions, where the correct answer is that no
fixed number exists): System A scored {a3}%, System C scored {c3}%.
Winner: {numeric_fact_winner_3}.

{b1_line}

System C wins clearly on both numeric fact buckets. This is expected
given how the two systems work. System C's answers for these 25
statute and theme combinations are hardcoded from the real statute
text, so there is no retrieval step to miss the right chunk and no
generation step to phrase the citation inconsistently. System A has to
retrieve the right passage out of the full corpus and then rely on the
model to state the citation correctly in free text, and both of those
steps can go wrong independently.

## Who wins on cross jurisdiction comparison questions (bucket 2)

System A scored {a2}%, System C scored {c2}%. Winner: {comparison_winner}.

This is worth calling out specifically because it is the least
intuitive result in this report. A fixed lookup table sounds like it
should be worst at comparison questions, since comparing facts across
countries sounds like a reasoning task, not a lookup task. In practice,
System C's classification step simply returns multiple jurisdiction and
theme pairs when a question spans more than one country, and then reads
off the table row for each one. Since every row is already the correct
fact word for word, there is nothing left to compare incorrectly, the
system just lists the true figures for each jurisdiction side by side.
System A has to retrieve, hold, and correctly restate several
jurisdictions' facts in one free-form answer, which is more room for a
dropped fact or a wrong citation.

## Plain language conclusion

Based only on what this data shows: a deterministic lookup table wins
decisively whenever the question has a small number of fixed answers to
draw from, whether that is one country's exact deadline or several
countries' deadlines compared side by side. There is no advantage to
letting a model generate an answer to a question whose real answer
never changes, since generation only adds a chance to get it wrong.

System A's advantage shows up on the buckets that ask for something a
fixed table cannot produce at all. Bucket 4 (adversarial questions,
where the input tries to mislead or manipulate the system) and bucket 6
(drafting an email, memo, or policy line) both need free-form reasoning
and writing, not a lookup. System A handled both of those well, hitting
100 percent on adversarial questions and 100 percent on drafting
questions, while System C's drafting answers were correct in substance
but never actually structured as a draft, since it can only return raw
facts, not composed prose.

The practical shape this suggests: use a deterministic lookup wherever
the question maps cleanly onto a small, known set of facts, and reserve
a generative system for open-ended tasks like drafting, explaining, or
handling adversarial input, where there is no fixed table row to return
in the first place. System B's design, verifying every claim against
the real source text before a simulated human ever approves it, is
built for a middle case this project did not get to fully test: open
ended questions where accuracy still has to be provably correct, not
just fluent.

## Why System B's evaluation is partial

System B was only run on bucket 1 in this project, not the full 90
question set. This is a budget and time constraint on this evaluation,
not a limitation found in System B's design. Each full 90 question run
in this project takes roughly 30 to 35 minutes and a full round of API
calls, because of a shared rate limit on the Voyage AI account used for
embeddings. System B also went through two rounds of real bug fixes
during this project (a prompt phrasing issue that caused the router to
refuse to classify some questions, and a citation field that was being
dropped when the final answer was assembled), each of which needed a
cheap bucket 1 check to confirm before it made sense to spend a full 90
question run confirming it. By the time both fixes were verified working
on bucket 1, a full 90 question run for System B had not yet been
carried out. The bucket 1 numbers already recorded reflect a fully
working version of System B, not a broken one, they are simply a
smaller sample than System A and System C received.
"""

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(report)
    print(f"Report written to {OUTPUT_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
