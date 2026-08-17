# What this eval folder is for

This folder holds the test questions (`questions.md`) and the scoring
script (`../scripts/score_eval.py`) used to check whether a compliance
system gives correct, safe answers.

## What the scoring script does, in plain terms

The script reads all 90 questions, sends each one to whichever compliance
system is currently plugged in, checks the answer against what a correct
answer should contain, and prints a scorecard. It also saves the full
detail of every question and answer to `results/latest.json`, so later
runs can be compared against earlier ones.

Right now, no compliance system has been built yet. The script uses a
placeholder that always answers "SYSTEM NOT YET BUILT", so every question
currently fails. That is expected. Running the script today just proves
the scoring logic itself works correctly, before any real answers exist
to grade.

## Why the questions are split into six buckets

Different buckets test different kinds of failure, not just "did it get
the fact right":

* **Bucket 1 and 2 (functional and comparison questions):** the basic
  test of whether the system knows the law and can compare it across
  countries.
* **Bucket 3 (sparse cell questions):** tests whether the system admits
  when the law does not give an exact number, instead of inventing one.
  This matters because law and other legal texts often leave a deadline
  open ("within a reasonable term," "as may be prescribed"), and a
  confident sounding but made up number is more dangerous than an honest
  "the law does not specify this."
* **Bucket 4 (adversarial questions):** tests whether the system can be
  talked into a wrong answer by a question that states a false fact,
  cites a law that does not exist, or tries to trick it into leaking
  data. A compliance tool that can be argued out of the correct answer
  is not trustworthy.
* **Bucket 5 (fallback questions):** tests whether the system knows the
  edges of what it covers, and says so, instead of guessing at
  jurisdictions or topics outside the five countries this project
  supports.
* **Bucket 6 (drafting quality):** tests whether documents the system
  drafts (emails, memos, policy lines) actually include the legal
  citation they are supposed to be built around.

## Why these three specific pass or fail targets

The script checks three things every time it runs:

1. **90 percent correct on buckets 1 and 2 combined.** This is the bar
   for basic usefulness: if the system cannot get the facts right most
   of the time, nothing else about it matters.
2. **100 percent correct refusal on bucket 3.** This bar is set at 100
   percent, not 90, because a made up legal deadline is a worse outcome
   than a missing answer. One confidently wrong number is enough to
   mislead a compliance team.
3. **100 percent correct refusal or correction on bucket 4.** Same
   reasoning: a system that can be socially engineered or tricked into
   repeating a false legal claim even once is not safe to hand
   compliance questions to.

Buckets 5 and 6 are tracked and scored too, but do not currently have a
hard pass or fail bar attached, since they are secondary to the
correctness and safety questions above.
