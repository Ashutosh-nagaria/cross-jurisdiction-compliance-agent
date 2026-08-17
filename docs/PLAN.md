# Chapter Plan

This project is built in chapters. Each chapter is a self contained step. Later
chapters depend on earlier ones being done first.

- **Chapter 0: Setup**
  Create the GitHub repo, the folder structure, the README, this plan, the
  environment variable template, the gitignore, and the Python environment.
  No product code yet.

- **Chapter 1: Assemble the statute corpus**
  Collect 23 real statute sections across 5 jurisdictions (EU GDPR, India
  DPDP, California CCPA/CPRA, Brazil LGPD, Singapore PDPA) and 5 recurring
  themes (breach notification, consent, data subject request deadlines, DPO
  requirement, cross-border transfer). Store the verbatim text and the exact
  citation for each section.

- **Chapter 2: Author the fictional company documents**
  Write 8 documents describing a made-up company: what personal data it
  holds, and its internal privacy policies. This gives the system something
  concrete to check against the statutes.

- **Chapter 3: Build the eval set**
  Write 90 test questions that the system should be able to answer, plus a
  script that scores answers automatically.

- **Chapter 4: Ingest data**
  Load the statute corpus and company documents into MongoDB Atlas Vector
  Search, using Voyage's law-domain embedding model to turn text into
  searchable vectors.

- **Chapter 5: Build System A (baseline RAG)**
  A standard retrieve-then-answer pipeline. Run the 90 question benchmark
  against it to get a baseline score.

- **Chapter 6: Improve retrieval**
  Add hybrid search (combining keyword and vector search) and reranking to
  System A, then measure whether that improves the benchmark score.

- **Chapter 7: Build System B (agent)**
  A LangGraph agent that extracts specific compliance obligations, checks
  each one against its source statute text, and drafts a policy based on
  what it found.

- **Chapter 8: Human approval step**
  Before any drafted obligation from System B is accepted, a person must
  review and approve it. Nothing gets treated as final without that
  approval.

- **Chapter 9: Build System C (rule lookup)**
  A deterministic lookup system for numeric facts (like "how many days to
  respond to a data subject request in Brazil"), with no model involved in
  producing the number itself.

- **Chapter 10: Compare all three systems**
  Run System A, System B, and System C on the same 90 question benchmark
  and publish the results side by side.

- **Chapter 11: Build the interface**
  A Streamlit web interface so the systems can be used without running code
  directly.

- **Chapter 12: Dockerize and deploy**
  Package the project so it can run the same way on any machine, and deploy
  it somewhere reachable.

- **Chapter 13: Write up results and lessons**
  A final document covering what worked, what did not, and what the
  benchmark results actually show.
