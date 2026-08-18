# Concepts

This document explains the same project four times, at four different
levels of depth. Read as far down as is useful and stop whenever it
stops being useful.

## Section 1: In plain terms

Imagine you need to know how many days a company has to report a data
breach in Brazil. There are a few ways you could find out.

You could look it up yourself in a paper rulebook. If the rule you
need is actually written down in the book, you will get the right
answer every time, worded exactly the way the book words it. But the
rulebook cannot explain anything it does not already contain, and it
cannot help you at all if your question is not really about looking
something up, it can only turn pages, never think.

You could ask a well read assistant instead. They have read a huge
amount and can explain things in their own words, compare several
countries at once, and write you a polished summary. Most of the time
they get it right. But they are working from memory and impression,
not from the book in front of them, so once in a while they will state
something with total confidence that turns out to be slightly wrong,
or borrow a detail from the wrong country by mistake.

Or you could ask that same assistant to show their work. Before they
give you an answer, they have to point to the exact page and sentence
their claim comes from, someone checks that the sentence they pointed
to actually says what they claim it says, and only after that check
passes does a supervisor sign off before the answer goes out the door.
This takes longer and involves more steps, but a wrong claim gets
caught before anyone sees it, not after.

This project builds all three of those approaches for real, as three
separate systems, and tests them against the same set of questions to
see which one is actually right, how often, and for what kind of
question. The rulebook is System C. The well read assistant is System
A. The assistant who shows their work is System B.

## Section 2: How it actually works

**Embeddings.** To let a computer search text by meaning instead of by
matching exact words, every piece of statute text is converted into an
embedding, a list of numbers that represents what that text means.
Two passages about a similar idea end up with similar number lists,
even if they do not share any of the same words. This project uses a
legal domain tuned embedding model rather than a general purpose one,
since legal language has its own vocabulary and structure that a model
trained mostly on general web text handles less precisely.

**Vector search.** Those embeddings are stored in a vector database.
When a question comes in, it gets turned into its own embedding, and
the database finds which stored passages have the closest embeddings
to the question, meaning the closest in meaning, not the closest in
exact wording. This is what lets a question worded differently from
the statute still find the right statute passage.

**The agent's structure (System B).** System B is built as a graph of
steps, where each step does one job and passes its work to the next
step:

1. A router step reads the question and decides which of the five
   supported jurisdictions are actually relevant to it.
2. A retrieval step runs a separate vector search for each relevant
   jurisdiction, so an answer about one country cannot accidentally
   pull in another country's text just because it happens to be
   similar.
3. An extraction step turns the retrieved text into a structured list
   of claims, where each claim is forced to include exactly which
   source file it came from and the exact quoted sentence that
   supports it, rather than letting the model just write a paragraph.
4. A verification step checks every one of those quotes against the
   real file on disk, word for word. Anything that does not match
   exactly is thrown out and never reaches the final answer.
5. A human approval step pauses the whole process and waits for an
   actual decision, approve or reject, before anything is treated as
   final. Nothing is shown as a finished answer without that step
   happening.

**The deterministic lookup (System C).** System C does not use vector
search or free form generation at all for the actual answer. It has a
fixed table of the real facts, copied directly from the statute text
by hand ahead of time. The only job an AI model does here is read the
question and decide which row (or rows, for a question spanning
several countries) of that table applies. The model is never allowed
to state the fact itself, only to point at which fact applies, which
is why System C cannot invent a wrong number, it simply has no path to
produce a number that was not already sitting in the table.

## Section 3: What actually broke, and what that taught me

**1. The baseline system sometimes cited a supporting document instead
of the primary source, even when the fact itself was correct.**
What happened: asked for an exact statutory deadline, the baseline
system sometimes answered correctly but cited an internal company
document that happened to restate the same figure, instead of citing
the actual statute section. Why: the system's prompt only instructed
it to cite the file a fact came from, it did not force it to name the
specific article or section label, so whichever source the model
reached for first in its own reasoning is what got cited. What it
means: being factually right and being properly sourced are two
different guarantees, and a system needs to be explicitly held to both
separately, since getting one right does not guarantee the other.

**2. The baseline system missed a real fact once because retrieval
only returned a section's header, not the paragraph containing the
actual number.**
What happened: a statute file's title and citation line got retrieved
as its own separate chunk of text, ahead of the paragraph that
actually contained the number being asked about, so the answer said
the information was not available even though it existed a few lines
further down in the same file. Why: the way the text was split into
searchable pieces treated a short header as equally competitive with a
full paragraph, and a short, generic looking header sometimes ranked
higher in a similarity search than expected. What it means: how text
gets chopped into pieces before search is not a minor implementation
detail, it directly determines what the system is even capable of
finding, no matter how good the model answering the question is.

**3. A quiet formatting mismatch in the ingestion pipeline caused every
primary source citation label to go missing, and it went unnoticed for
a long stretch of this project before a stricter downstream check
exposed it.**
What happened: the code responsible for tagging each piece of text
with which statute section it came from relied on a pattern that only
matched when a heading stood entirely alone. Every real statute file
in this project had its heading immediately followed by a couple of
metadata lines with no blank line in between, so the pattern silently
never matched for any of them, and every single citation label came
back empty. Why it stayed hidden: the system still worked and produced
plausible sounding answers regardless, since a missing label is not an
error a program can complain about on its own, it is just quietly
useless data sitting in a field nobody was strictly checking against
its intended purpose yet. What it means: a bug that produces no
error message and does not stop anything from running can still be
completely wrong, and the only way it surfaced here was building a
stricter component downstream that actually depended on that field
being correct.

**4. The verified agent's citations are structurally more reliable
than the baseline's, because they get assembled mechanically from
source metadata rather than left to the model to remember and
mention.**
What happened: once the agent's final answer was changed to
automatically pull the citation label from the exact chunk each quote
was verified against, instead of hoping the model happened to mention
it in its own sentence, citations started appearing consistently.
Why: a model choosing whether to restate a fact is a probability, not
a guarantee, but code that always looks a specific field up and
appends it is a guarantee, restated every single time with no
variance. What it means: for anything that has to be reliably present
in an answer, not just usually present, it is worth building a
mechanical step that assembles it directly, rather than trusting a
generative step to remember to include it.

**5. The deterministic lookup system has no concept of intent at all,
it will attempt to answer even a manipulative or adversarial question,
since it has no judgment layer, only classification and lookup.**
What happened: given a question deliberately phrased to try to extract
information it should refuse, the lookup system classified it to the
nearest matching topic and returned the corresponding table row
anyway, rather than recognizing anything was wrong with the request.
Why: this system was built to do exactly two things, decide which
table row a question maps to, and return that row's contents. It was
never given any step whose job is to evaluate whether a question
should be answered at all. What it means: accuracy and safety are not
the same property, and a system that is extremely accurate within its
narrow lane can still have zero ability to recognize when a question
is trying to misuse that lane, unless a refusal capability is
deliberately built in as its own step.

**6. The evaluation grading logic itself needed several rounds of
refinement, since automated grading is its own design problem, not a
solved, neutral yardstick.**
What happened: the first version of the grading logic required an
answer to contain an expected fact as one exact, word for word phrase.
Answers that were completely correct but phrased slightly differently,
using a different word order, a different spelling convention, or a
description instead of the exact keyword, were marked wrong. Fixing
this took several passes: first extracting individual key facts
instead of one whole phrase, then adding pattern based checks for
behaviors like refusal or correction instead of exact wording, then
adding tolerance for spelling and word form variation. What it means:
an automated grader is itself a piece of software with its own bugs
and its own design assumptions, and a low score can just as easily
mean the grader is too strict as it can mean the system being graded
is actually wrong, so a grader has to be inspected and trusted just as
carefully as the thing it is grading.

## Section 4: Known limitations and what a v2 would add

**Hybrid search.** This project's retrieval relies entirely on meaning
based similarity search. A v2 would add hybrid search, combining that
with plain keyword matching, so a question that uses an exact term
straight out of the statute is guaranteed to find the passage
containing that term, rather than relying only on the embedding model
to recognize the connection.

**Uneven evaluation coverage.** Two of the three systems in this
project were evaluated on the full 90 question benchmark. The third,
the verified agentic pipeline, was only evaluated on a smaller slice
of that benchmark, due to a fixed time and cost budget for this
project rather than any limitation found in that system's design. A
v2 would complete that evaluation before drawing any final conclusion
about that system's real accuracy.

**Interface polish.** The current interface is intentionally built for
function over form, a working way to ask each system a question and
see its answer and citations side by side. A v2 would spend real
design effort on the interface itself, since right now it prioritizes
being correct and honest about what each system did over looking
finished.
