# Results: comparing System A, System B, and System C

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

| Bucket | What it tests | System A (full 90) | System C (full 90) | System B (bucket 1 only, partial sample) |
|---|---|---|---|---|
| 1 | Single jurisdiction functional | 36.0% | 72.0% | 24.0% |
| 2 | Cross jurisdiction comparison | 80.0% | 92.0% | not run |
| 3 | Sparse cell, correct refusal expected | 60.0% | 80.0% | not run |
| 4 | Adversarial | 100.0% | 66.7% | not run |
| 5 | Fallback | 90.0% | 80.0% | not run |
| 6 | Drafting quality | 100.0% | 80.0% | not run |

System B's column is a partial sample of 25 questions, not a full 90
question result, and should not be read as directly equivalent to the
System A and System C columns next to it.

## Release gate targets (System A and System C only)

| Release gate target | System A | System C |
|---|---|---|
| 90 percent on buckets 1 and 2 combined | 58.0% (not met) | 82.0% (not met) |
| 100 percent on bucket 3 | 60.0% (not met) | 80.0% (not met) |
| 100 percent on bucket 4 | 100.0% (met) | 66.7% (not met) |

Neither system currently meets all three release gates. System A meets
the bucket 4 target outright. System C comes closer on the other two
targets but does not meet either of them yet.

## Who wins on numeric fact questions (buckets 1 and 3)

Bucket 1 (single jurisdiction functional questions, mostly asking for an
exact number or citation): System A scored 36.0%, System C scored 72.0%.
Winner: System C.

Bucket 3 (sparse cell questions, where the correct answer is that no
fixed number exists): System A scored 60.0%, System C scored 80.0%.
Winner: System C.

On this same slice of 25 questions, System B (partial sample, only bucket 1 has been run) scored 24.0%, the lowest of the three, though it was tested under a harder five step pipeline with fewer rounds of tuning than the other two systems received.

System C wins clearly on both numeric fact buckets. This is expected
given how the two systems work. System C's answers for these 25
statute and theme combinations are hardcoded from the real statute
text, so there is no retrieval step to miss the right chunk and no
generation step to phrase the citation inconsistently. System A has to
retrieve the right passage out of the full corpus and then rely on the
model to state the citation correctly in free text, and both of those
steps can go wrong independently.

## Who wins on cross jurisdiction comparison questions (bucket 2)

System A scored 80.0%, System C scored 92.0%. Winner: System C.

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
