# Cross Jurisdiction Compliance Agent

Compliance teams that operate across multiple countries often need to
answer questions like "how many days do we have to report a data
breach," and the correct answer depends entirely on which country's
law applies, each with its own statute, its own wording, and its own
deadline. This project explores what it takes to build an AI system
that can answer cross jurisdiction data privacy questions accurately,
citing the exact statute section behind each answer, across five
jurisdictions: the European Union, India, California, Brazil, and
Singapore.

## Three approaches, compared head to head

Rather than building one system and assuming it works, this project
builds and evaluates three different approaches to the same problem,
using the same 90 question benchmark.

- **System A** is a baseline retrieval and answer system. It searches
  the statute text for relevant passages and lets an AI model write
  the answer in its own words, citing where each fact came from.
- **System B** is a more careful, multi step agent. It figures out
  which country a question is about, retrieves text separately for
  each one, pulls out individual factual claims, verifies every claim
  word for word against the real statute text, and pauses for a human
  to approve the answer before it counts as final.
- **System C** is a deterministic rule lookup. It uses an AI model
  only to classify which jurisdiction and topic a question is about,
  then returns a fixed answer built directly from the real statute
  text. It cannot generate a wrong number, because it never generates
  a number at all.

## Headline result

A deterministic lookup table wins decisively on questions that have a
small, fixed set of correct answers, whether that is one country's
exact deadline or several countries' deadlines compared side by side,
since there is no retrieval step to miss and no generation step to get
the citation wrong. The baseline retrieval system's advantage shows up
on the questions a fixed table cannot handle at all: correcting a
misleading or adversarial claim, and drafting an actual document
rather than just stating a fact. See [docs/RESULTS.md](docs/RESULTS.md)
for the full numbers, and [concepts.md](concepts.md) for a deeper
explanation of why each system behaves the way it does.

## Running it

The easiest way to try this interactively is the Streamlit interface:

    streamlit run app.py

This lets you ask any of the three systems a question, see its
citations, and for System B specifically, approve or reject its answer
yourself before it is treated as final, the same way a real reviewer
would. See [DEPLOY.md](DEPLOY.md) for how to build and run the whole
thing in a container instead.

## Status

This project's full build is complete, chapter by chapter. See
[docs/PLAN.md](docs/PLAN.md) for the chapter history and
[docs/RESULTS.md](docs/RESULTS.md) for the full evaluation results.
