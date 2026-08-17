# Cross Jurisdiction Compliance Agent

## The problem

Companies that operate in more than one country have to follow more than one
data privacy law at once. A single question like "how fast do we have to
report a data breach" has a different answer in the EU, India, California,
Brazil, and Singapore, each with its own statute, its own wording, and its
own deadline. Today, compliance teams answer these questions by manually
reading the statutes and cross-checking them against internal company
policy. That is slow, easy to get wrong, and hard to audit later, since
there is often no clear record of which exact statute section an answer
came from.

## The approach

This project builds an AI system that answers cross-jurisdiction data
privacy compliance questions and cites the exact statute section it used for
each answer, across five jurisdictions: EU GDPR, India DPDP, California
CCPA/CPRA, Brazil LGPD, and Singapore PDPA.

Rather than building one system and assuming it works, this project builds
three different retrieval and reasoning systems and compares them head to
head on the same benchmark of test questions:

- **System A**, a baseline retrieval system (standard RAG, retrieve then
  answer).
- **System B**, an agent that extracts specific compliance obligations,
  verifies each one against the source statute text, and drafts a policy,
  with a required human approval step before any draft is accepted.
- **System C**, a deterministic rule lookup for questions that have a single
  correct numeric answer (like a deadline in days), with no model involved
  in producing that number.

Comparing three systems on one benchmark makes it possible to see where a
plain retrieval system is good enough, and where an agent with verification
and human approval is actually needed.

## Status

This project is in progress. See [docs/PLAN.md](docs/PLAN.md) for the full
chapter by chapter plan, from initial setup through to a deployed interface
and a final results writeup.
