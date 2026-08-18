"""
System B: the verifying LangGraph agent (Chapter 7).

Unlike System A, which retrieves once and lets Claude write a free-form
answer, System B breaks answering a question into five separate steps
wired together as a LangGraph graph, with a verification step that
checks every claim against the real source text before it is allowed
into the final answer, and a human approval step before anything is
released.

The five steps, in order:
1. Router: figure out which of the five jurisdictions matter here.
2. Retrieval: search each relevant jurisdiction separately, so answers
   about one country cannot accidentally pull in another country's text.
3. Extraction: turn the retrieved text into a structured list of
   claims, each one tied to an exact source file and an exact quoted
   span, using Pydantic so Claude cannot slip into free-form prose here.
4. Verification: check that each quoted span is really in the source
   file, word for word. Anything that does not check out is rejected
   and left out of the final answer.
5. Human approval: pause before finalizing anything, using LangGraph's
   interrupt() feature. In a real deployment, this is where a human
   compliance reviewer would look at the verified claims and either
   approve or reject them before they go out. This project has no
   human reviewer available during automated scoring, so it logs what
   the reviewer would have seen and then simulates an approval. A real
   product must not skip this step the way this script does.
"""

import os
import re
import time
import uuid
from pathlib import Path
from typing import List, TypedDict

import voyageai
from anthropic import Anthropic
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.environ["MONGODB_URI"]
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "corpus"

DATABASE_NAME = "compliance_agent"
COLLECTION_NAME = "compliance_chunks"
VECTOR_INDEX_NAME = "compliance_chunks_vector_index"
EMBEDDING_MODEL = "voyage-law-2"
CLAUDE_MODEL = "claude-sonnet-5"

VALID_JURISDICTIONS = [
    "eu-gdpr",
    "india-dpdp",
    "california",
    "brazil-lgpd",
    "singapore-pdpa",
]
TOP_K_PER_JURISDICTION = 5
NUM_CANDIDATES = 60

# Same Voyage AI free tier pacing as System A (see src/system_a.py and
# Chapter 4), since this project's Voyage account has no payment method
# on file and is capped at 3 requests per minute.
SECONDS_BETWEEN_VOYAGE_CALLS = 21
_last_voyage_call_time = 0.0

_voyage_client = None
_mongo_collection = None
_anthropic_client = None
_graph = None


def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        _voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    return _voyage_client


def _get_mongo_collection():
    global _mongo_collection
    if _mongo_collection is None:
        client = MongoClient(MONGODB_URI)
        _mongo_collection = client[DATABASE_NAME][COLLECTION_NAME]
    return _mongo_collection


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


# --- Structured output shapes ---------------------------------------
#
# These Pydantic models describe exactly what shape we force Claude's
# output into, using the Anthropic API's tool-calling feature: instead
# of asking Claude to write prose and hoping it follows a format, we
# hand it a schema as a "tool" and require it to call that tool, so the
# response comes back as data we can parse directly, not text we have
# to guess at.


class JurisdictionRouting(BaseModel):
    relevant_jurisdictions: List[str] = Field(
        description=(
            "Which jurisdiction folders are relevant to answering this "
            "question. Must only contain values from this exact list: "
            "eu-gdpr, india-dpdp, california, brazil-lgpd, "
            "singapore-pdpa. Return an empty list if none of these five "
            "are relevant to the question."
        )
    )


class Claim(BaseModel):
    claim: str = Field(
        description="One factual claim that helps answer the question, stated in plain language."
    )
    source_file: str = Field(
        description=(
            "The exact relative_path value of the chunk this claim is "
            "drawn from, copied exactly as given in the retrieved "
            "chunks, for example corpus/statutes/eu-gdpr/breach-notification.md"
        )
    )
    quoted_text: str = Field(
        description=(
            "The exact verbatim text span from that chunk's text that "
            "supports this claim, copied word for word with no "
            "paraphrasing, so it can be checked against the real file."
        )
    )


class ExtractedClaims(BaseModel):
    claims: List[Claim] = Field(
        description=(
            "All factual claims extracted from the retrieved chunks "
            "that help answer the question. Empty list if the chunks "
            "do not contain enough information to answer it."
        )
    )


def call_claude_structured(prompt, tool_name, tool_description, input_schema):
    """
    Sends a prompt to Claude and forces the response into the given
    JSON schema by handing it to Claude as a required tool call, rather
    than asking for free text and hoping it comes back parseable.
    """
    client = _get_anthropic_client()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        tools=[
            {
                "name": tool_name,
                "description": tool_description,
                "input_schema": input_schema,
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError(f"Claude did not return a tool call for {tool_name}")


def embed_question(question):
    """
    Turns the question into a Voyage AI embedding, same model and same
    free tier pacing as System A (see src/system_a.py for the full
    explanation of why the pacing exists).
    """
    global _last_voyage_call_time

    elapsed = time.monotonic() - _last_voyage_call_time
    wait_needed = SECONDS_BETWEEN_VOYAGE_CALLS - elapsed
    if wait_needed > 0:
        time.sleep(wait_needed)

    client = _get_voyage_client()
    while True:
        try:
            result = client.embed([question], model=EMBEDDING_MODEL, input_type="query")
            break
        except voyageai.error.RateLimitError:
            print("Voyage rate limit hit, waiting 30 seconds before retrying...")
            time.sleep(30)

    _last_voyage_call_time = time.monotonic()
    return result.embeddings[0]


# --- Graph state -------------------------------------------------------
#
# This is the shared notebook every node in the graph reads from and
# writes to. Each node only fills in its own piece, and later nodes can
# see what earlier nodes wrote.


class GraphState(TypedDict):
    question: str
    jurisdictions: List[str]
    retrieved_chunks: List[dict]
    claims: List[dict]
    verified_claims: List[dict]
    rejected_claims: List[dict]
    final_answer: str


# --- Node 1: Router ------------------------------------------------------


def route_jurisdictions_node(state):
    """
    Step 1: asks Claude which of the five supported jurisdictions are
    actually relevant to this question, so the next step only searches
    the jurisdictions that matter instead of everything at once.
    """
    prompt = (
        "You are classifying which data privacy jurisdictions are "
        "relevant to a compliance question, out of five supported "
        "jurisdictions:\n\n"
        "- eu-gdpr: European Union, GDPR\n"
        "- india-dpdp: India, Digital Personal Data Protection Act\n"
        "- california: California, CCPA/CPRA\n"
        "- brazil-lgpd: Brazil, LGPD\n"
        "- singapore-pdpa: Singapore, PDPA\n\n"
        f"Question: {state['question']}\n\n"
        "List which of these five jurisdiction keys are relevant to "
        "this question. Return an empty list if none of them apply."
    )
    result = call_claude_structured(
        prompt,
        "route_jurisdictions",
        "Selects which of the five supported jurisdictions are relevant to a question.",
        JurisdictionRouting.model_json_schema(),
    )
    candidates = result.get("relevant_jurisdictions", [])
    valid = [j for j in candidates if j in VALID_JURISDICTIONS]
    return {"jurisdictions": valid}


# --- Node 2: Retrieval ---------------------------------------------------


def vector_search_one_jurisdiction(question_embedding, jurisdiction, top_k):
    """
    Runs one Atlas Vector Search query restricted to a single
    jurisdiction, using the filter field set up on the index in
    Chapter 4. Doing one filtered search per jurisdiction, instead of
    one search across everything, is what stops an EU question from
    accidentally pulling in Brazilian or Indian text just because it
    happens to be semantically similar.
    """
    collection = _get_mongo_collection()
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": question_embedding,
                "filter": {"jurisdiction": {"$eq": jurisdiction}},
                "numCandidates": NUM_CANDIDATES,
                "limit": top_k,
            }
        },
        {"$project": {"embedding": 0}},
    ]
    return list(collection.aggregate(pipeline))


def retrieve_chunks_node(state):
    """
    Step 2: embeds the question once, then runs one filtered vector
    search per relevant jurisdiction found by the router, and combines
    the results. If the router found no relevant jurisdiction, this
    step retrieves nothing, and the rest of the graph will correctly
    end up saying it cannot answer instead of guessing.
    """
    if not state["jurisdictions"]:
        return {"retrieved_chunks": []}

    question_embedding = embed_question(state["question"])
    all_chunks = []
    for jurisdiction in state["jurisdictions"]:
        chunks = vector_search_one_jurisdiction(
            question_embedding, jurisdiction, TOP_K_PER_JURISDICTION
        )
        all_chunks.extend(chunks)
    return {"retrieved_chunks": all_chunks}


# --- Node 3: Extraction --------------------------------------------------


def build_extraction_prompt(question, chunks):
    labeled_chunks = []
    for i, chunk in enumerate(chunks, start=1):
        labeled_chunks.append(
            f"[Chunk {i}]\n"
            f"Source file: {chunk['relative_path']}\n"
            f"Jurisdiction: {chunk['jurisdiction']}\n"
            f"Section: {chunk.get('section') or 'none'}\n"
            f"Text:\n{chunk['text']}\n"
        )
    chunks_block = "\n".join(labeled_chunks)

    return (
        "You are extracting factual claims that help answer a "
        "compliance question, using ONLY the retrieved text chunks "
        "below. For each distinct fact you find that helps answer the "
        "question, extract one claim with the claim itself in plain "
        "language, the exact source_file it came from (copy the "
        "Source file value exactly as given), and quoted_text, an "
        "exact word for word copy of the specific text span from that "
        "chunk supporting the claim. Do not paraphrase quoted_text, "
        "copy it exactly as written. If the chunks do not contain "
        "enough information to answer the question, return an empty "
        "list of claims rather than guessing.\n\n"
        f"Question: {question}\n\n"
        f"Retrieved chunks:\n{chunks_block}"
    )


def extract_claims_node(state):
    """
    Step 3: turns the retrieved chunks into a structured list of
    claims. Forcing this through the Claim schema (see
    call_claude_structured above) means Claude cannot just write a
    paragraph, it has to commit to a specific source file and a
    specific quoted span for every claim, which is exactly what the
    next step needs to check.
    """
    if not state["retrieved_chunks"]:
        return {"claims": []}

    prompt = build_extraction_prompt(state["question"], state["retrieved_chunks"])
    result = call_claude_structured(
        prompt,
        "extract_claims",
        "Extracts factual claims from retrieved text, each tied to an exact source file and quoted span.",
        ExtractedClaims.model_json_schema(),
    )
    return {"claims": result.get("claims", [])}


# --- Node 4: Verification -------------------------------------------------


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text or "").strip()


def claim_is_verified(claim):
    """
    Checks a single claim's quoted_text against the real file on disk,
    not against the chunk text Claude was given, so this step catches
    both a fabricated quote and (in theory) a corrupted or stale chunk.
    Whitespace is normalized on both sides before comparing, since line
    wrapping differences should not fail an otherwise word for word
    match, but the actual words must still match exactly.
    """
    source_file = claim.get("source_file", "")
    quoted_text = claim.get("quoted_text", "")
    if not source_file or not quoted_text:
        return False

    file_path = (REPO_ROOT / source_file).resolve()
    # Refuse to read anything outside the corpus folder, even though a
    # forced structured field makes this unlikely to happen, this is
    # a cheap safety check against a claim pointing somewhere it should not.
    if not str(file_path).startswith(str(CORPUS_ROOT.resolve())):
        return False
    if not file_path.is_file():
        return False

    file_text = file_path.read_text()
    return normalize_whitespace(quoted_text) in normalize_whitespace(file_text)


def verify_claims_node(state):
    """
    Step 4: the core safety check of System B. Every claim extracted in
    step 3 gets checked here, and only the ones whose quoted text
    genuinely appears in the real source file survive. Anything that
    does not check out, whether from a model mistake, a hallucinated
    quote, or a wrong file reference, gets rejected here and never
    reaches the final answer.
    """
    verified = []
    rejected = []
    for claim in state["claims"]:
        if claim_is_verified(claim):
            verified.append(claim)
        else:
            rejected.append(claim)
    return {"verified_claims": verified, "rejected_claims": rejected}


# --- Node 5: Human approval ------------------------------------------------


def find_citation_for_claim(claim, retrieved_chunks):
    """
    Looks up the exact chunk a claim's quoted_text came from, by
    matching the claim's source_file and quoted_text against the
    chunks that were actually retrieved, and returns that chunk's
    section label (its citation, e.g. "GDPR Article 33: Notification
    of a personal data breach..."). This pulls the citation straight
    from data already gathered during retrieval, instead of relying on
    Claude to correctly restate the article or section number in its
    own words when writing the claim, which it does not always do.
    """
    normalized_quote = normalize_whitespace(claim.get("quoted_text", ""))
    if not normalized_quote:
        return None

    for chunk in retrieved_chunks:
        if chunk.get("relative_path") != claim.get("source_file"):
            continue
        if normalized_quote in normalize_whitespace(chunk.get("text", "")):
            return chunk.get("section")
    return None


def build_final_answer(verified_claims, rejected_claims, retrieved_chunks):
    if not verified_claims:
        note = ""
        if rejected_claims:
            note = (
                f" {len(rejected_claims)} claim(s) were extracted but "
                "rejected because their quoted text could not be "
                "verified word for word against the actual source "
                "file, so they were left out."
            )
        return "The retrieved and verified information does not answer this question." + note

    lines = []
    for claim in verified_claims:
        citation = find_citation_for_claim(claim, retrieved_chunks)
        citation_part = f"; {citation}" if citation else ""
        lines.append(f"- {claim['claim']} (Source: {claim['source_file']}{citation_part})")
    answer = "\n".join(lines)

    if rejected_claims:
        answer += (
            f"\n\nNote: {len(rejected_claims)} additional claim(s) were "
            "extracted but rejected during verification because their "
            "quoted text did not match the source file word for word, "
            "so they were left out of this answer."
        )

    return answer


def human_approval_node(state):
    """
    Step 5: pauses the graph here using LangGraph's interrupt()
    function, and hands back exactly what a human compliance reviewer
    would need to see: the verified claims that are about to become
    the final answer, and the rejected claims that got filtered out
    and why. In a real deployment, the graph would stay paused here,
    potentially for hours or days, until a real person reviewed this
    and approved or rejected it through some interface. Whatever they
    decide gets sent back in with LangGraph's Command(resume=...),
    and only then does this node continue.

    This project has no human reviewer available while running an
    automated 90 question eval, so the code that calls this graph
    (see answer_question below) auto-approves immediately after
    logging what the reviewer would have seen. That auto-approval is a
    simulation for this project only. A real deployment must not skip
    a real human decision here.
    """
    review_payload = {
        "question": state["question"],
        "verified_claims": state["verified_claims"],
        "rejected_claims": state["rejected_claims"],
    }
    decision = interrupt(review_payload)

    if decision.get("approved"):
        final_answer = build_final_answer(
            state["verified_claims"], state["rejected_claims"], state["retrieved_chunks"]
        )
    else:
        final_answer = "This answer was not approved for release."

    return {"final_answer": final_answer}


# --- Graph wiring ----------------------------------------------------------


def _build_graph():
    graph_builder = StateGraph(GraphState)
    graph_builder.add_node("route", route_jurisdictions_node)
    graph_builder.add_node("retrieve", retrieve_chunks_node)
    graph_builder.add_node("extract", extract_claims_node)
    graph_builder.add_node("verify", verify_claims_node)
    graph_builder.add_node("approve", human_approval_node)

    graph_builder.add_edge(START, "route")
    graph_builder.add_edge("route", "retrieve")
    graph_builder.add_edge("retrieve", "extract")
    graph_builder.add_edge("extract", "verify")
    graph_builder.add_edge("verify", "approve")
    graph_builder.add_edge("approve", END)

    # A checkpointer is required for interrupt()/Command(resume=...) to
    # work at all, it is what lets the graph remember where it paused
    # so it can pick back up later instead of starting over.
    return graph_builder.compile(checkpointer=MemorySaver())


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def answer_question(question):
    """
    Runs the full System B pipeline for one question: route, retrieve,
    extract, verify, and pause for approval. Since there is no human
    reviewer available during automated scoring, this function detects
    the pause, logs what a reviewer would have seen, and resumes the
    graph with a simulated approval so scoring can continue
    unattended. A real deployment would replace this auto-approval
    with an actual human decision coming back from a review interface.
    """
    graph = _get_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "question": question,
        "jurisdictions": [],
        "retrieved_chunks": [],
        "claims": [],
        "verified_claims": [],
        "rejected_claims": [],
        "final_answer": "",
    }

    result = graph.invoke(initial_state, config=config)

    if "__interrupt__" in result:
        review_payload = result["__interrupt__"][0].value
        print(
            "[human approval simulated] a real reviewer would see "
            f"{len(review_payload['verified_claims'])} verified claim(s) and "
            f"{len(review_payload['rejected_claims'])} rejected claim(s) for "
            f"the question: {review_payload['question']}"
        )
        result = graph.invoke(Command(resume={"approved": True}), config=config)

    return {
        "answer": result["final_answer"],
        "retrieved_chunks": result["retrieved_chunks"],
        "verified_claims": result["verified_claims"],
        "rejected_claims": result["rejected_claims"],
    }


# --- Interactive approval, used by the Streamlit app (Chapter 11) ------
#
# answer_question above auto-approves immediately, since the eval script
# runs unattended and there is no person available to click anything.
# The web app is different: a real person is looking at the page, so
# the app should actually pause and wait for them to click Approve or
# Reject, the way a real deployment would. These two functions split
# answer_question's single call into two steps so the app can put a
# real button in between them.


def start_question(question):
    """
    Runs System B up through the human approval pause, and returns
    what a reviewer needs to see, without deciding anything. Call
    resume_with_decision afterward with the same thread_id once a
    person has actually made a decision.
    """
    graph = _get_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "question": question,
        "jurisdictions": [],
        "retrieved_chunks": [],
        "claims": [],
        "verified_claims": [],
        "rejected_claims": [],
        "final_answer": "",
    }

    result = graph.invoke(initial_state, config=config)

    if "__interrupt__" not in result:
        # Should not normally happen, the graph always pauses at the
        # approval node, but handle it rather than crash if it does.
        return {
            "thread_id": thread_id,
            "question": question,
            "verified_claims": result.get("verified_claims", []),
            "rejected_claims": result.get("rejected_claims", []),
        }

    review_payload = result["__interrupt__"][0].value
    return {
        "thread_id": thread_id,
        "question": question,
        "verified_claims": review_payload["verified_claims"],
        "rejected_claims": review_payload["rejected_claims"],
    }


def resume_with_decision(thread_id, approved):
    """
    Resumes a paused System B run with a real decision from a human
    reviewer, and returns the final answer. approved should be True
    for an actual Approve click, False for Reject.
    """
    graph = _get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume={"approved": approved}), config=config)
    return {
        "answer": result["final_answer"],
        "retrieved_chunks": result["retrieved_chunks"],
        "verified_claims": result["verified_claims"],
        "rejected_claims": result["rejected_claims"],
    }
