"""
Chapter 4: reads every statute and company document, breaks each one into
small, meaningful chunks, turns each chunk into an embedding (a list of
numbers that represents what the text means, used later for search), and
stores everything in MongoDB Atlas so the compliance system can look up
relevant text when answering a question.

Run this after filling in .env with a real MONGODB_URI and VOYAGE_API_KEY.
"""

import os
import re
import time
from pathlib import Path

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient, ReplaceOne

# Step 0: load the two secret values (database connection string and
# Voyage API key) from the .env file, instead of writing them into this
# script where they could accidentally get committed to GitHub.
load_dotenv()
MONGODB_URI = os.environ["MONGODB_URI"]
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUTES_DIR = REPO_ROOT / "corpus" / "statutes"
COMPANY_DIR = REPO_ROOT / "corpus" / "company"

DATABASE_NAME = "compliance_agent"
COLLECTION_NAME = "compliance_chunks"
EMBEDDING_MODEL = "voyage-law-2"
EXPECTED_DIMENSION = 1024  # voyage-law-2's known embedding size, checked against the real API response below
BATCH_SIZE = 12  # how many chunks we send to Voyage in one API call
# The Voyage account this project uses has no payment method on file yet,
# which caps it at 3 requests per minute and 10,000 tokens per minute
# (a free tier limit, not something wrong with this code). Waiting 21
# seconds between requests keeps us under 3 per minute with a safety
# margin, and the small BATCH_SIZE above keeps each request's token count
# well under the 10,000 token cap.
SECONDS_BETWEEN_REQUESTS = 21

# A markdown header line looks like "# Title", "## Title", "### Title", and so on.
HEADER_LINE_RE = re.compile(r"^#+\s+(.*)$")

# This finds every "paragraph" in a file: one or more lines in a row with
# no blank line between them. A blank line always starts a new paragraph.
# This is what lets us split on paragraph breaks instead of a fixed
# number of characters, so we never cut a sentence in half.
PARAGRAPH_RE = re.compile(r"[^\n]+(?:\n[^\n]+)*")


def collect_source_files():
    """Finds every markdown file in corpus/statutes/ and corpus/company/."""
    statute_files = sorted(STATUTES_DIR.glob("*/*.md"))
    company_files = sorted(COMPANY_DIR.glob("*.md"))
    return statute_files + company_files


def classify_file(path):
    """
    Works out which jurisdiction and theme a file belongs to, just from
    its folder and filename, since we already named things consistently
    back in Chapters 1 and 2.
    """
    relative_path = path.relative_to(REPO_ROOT)
    if path.parent.parent.name == "statutes":
        return {
            "doc_type": "statute",
            "jurisdiction": path.parent.name,
            "theme": path.stem,
            "relative_path": str(relative_path),
        }
    return {
        "doc_type": "company",
        "jurisdiction": "company",
        "theme": path.stem,
        "relative_path": str(relative_path),
    }


def chunk_file(path):
    """
    Splits one file into chunks along paragraph boundaries, and tags each
    chunk with the markdown header it falls under (its "section"), plus
    the exact character start and end position of that chunk in the
    original file. The offsets are what let us later prove a citation is
    real, by pointing back to the exact spot in the source file.
    """
    raw_text = path.read_text()
    metadata = classify_file(path)

    chunks = []
    current_section = None

    for match in PARAGRAPH_RE.finditer(raw_text):
        block_text = match.group()
        start, end = match.start(), match.end()

        # Only test the block's first line against the header pattern,
        # not the whole block. Statute file headers are followed
        # immediately by "Source:" and "Retrieved:" lines with no blank
        # line in between, so a header block is often more than one
        # line long. Matching against the whole block would require the
        # header to be the entire block with nothing after it, which
        # silently failed for every statute file, since their headers
        # always have those two lines glued on. Company docs happened
        # to have a blank line after each header, so they were not
        # affected and this went unnoticed.
        first_line = block_text.split("\n", 1)[0]
        header_match = HEADER_LINE_RE.match(first_line)
        if header_match:
            current_section = header_match.group(1).strip()

        chunks.append(
            {
                **metadata,
                "chunk_index": len(chunks),
                "section": current_section,
                "char_start": start,
                "char_end": end,
                "text": block_text,
            }
        )

    return chunks


def embed_chunks(voyage_client, chunks):
    """
    Sends the chunk text to Voyage AI in small batches and gets back one
    embedding per chunk. input_type="document" tells Voyage this text is
    something to be searched later, as opposed to a search query itself,
    which the API treats slightly differently for better results.

    Waits between batches and retries on a rate limit error, since this
    project's Voyage account is currently on the free tier's reduced
    rate limit (see SECONDS_BETWEEN_REQUESTS above).
    """
    embeddings = []
    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_number, batch_start in enumerate(range(0, len(chunks), BATCH_SIZE), start=1):
        batch = chunks[batch_start : batch_start + BATCH_SIZE]
        texts = [chunk["text"] for chunk in batch]

        print(f"Embedding batch {batch_number} of {total_batches}...")
        while True:
            try:
                result = voyage_client.embed(
                    texts, model=EMBEDDING_MODEL, input_type="document"
                )
                break
            except voyageai.error.RateLimitError:
                print("Rate limit hit, waiting 30 seconds before retrying...")
                time.sleep(30)

        embeddings.extend(result.embeddings)

        is_last_batch = batch_number == total_batches
        if not is_last_batch:
            time.sleep(SECONDS_BETWEEN_REQUESTS)

    return embeddings


def main():
    files = collect_source_files()
    print(f"Found {len(files)} source documents.")

    all_chunks = []
    for path in files:
        all_chunks.extend(chunk_file(path))
    print(f"Split into {len(all_chunks)} chunks.")

    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    embeddings = embed_chunks(voyage_client, all_chunks)

    actual_dimension = len(embeddings[0])
    if actual_dimension != EXPECTED_DIMENSION:
        print(
            f"Warning: voyage-law-2 returned {actual_dimension}-dimensional "
            f"embeddings, not the expected {EXPECTED_DIMENSION}. "
            "Update EXPECTED_DIMENSION here and the dimension in "
            "scripts/create_vector_index.py to match."
        )

    mongo_client = MongoClient(MONGODB_URI)
    collection = mongo_client[DATABASE_NAME][COLLECTION_NAME]

    # We use replace_one with upsert instead of a plain insert, so running
    # this script again later (say, after fixing a chunk) updates the
    # existing record instead of creating a duplicate. Each chunk gets a
    # stable ID built from its file path and position in that file.
    operations = []
    for chunk, embedding in zip(all_chunks, embeddings):
        chunk_id = f"{chunk['relative_path']}::{chunk['chunk_index']}"
        document = {"_id": chunk_id, "embedding": embedding, **chunk}
        operations.append(ReplaceOne({"_id": chunk_id}, document, upsert=True))

    result = collection.bulk_write(operations)
    upserted_or_matched = result.upserted_count + result.matched_count

    # Step 6: print the summary the user asked for.
    print()
    print("Ingestion summary")
    print(f"Total chunks created: {len(all_chunks)}")
    print(f"Total chunks embedded: {len(embeddings)}")
    print(
        f"Total chunks written to MongoDB: {upserted_or_matched} "
        f"(new: {result.upserted_count}, updated: {result.matched_count})"
    )
    print(
        "Insert count matches chunk count: "
        f"{upserted_or_matched == len(all_chunks)}"
    )
    print()

    print("Chunks per jurisdiction (statute files):")
    jurisdiction_counts = {}
    for chunk in all_chunks:
        if chunk["doc_type"] == "statute":
            jurisdiction_counts[chunk["jurisdiction"]] = (
                jurisdiction_counts.get(chunk["jurisdiction"], 0) + 1
            )
    for jurisdiction, count in sorted(jurisdiction_counts.items()):
        print(f"  {jurisdiction}: {count}")

    print()
    print("Chunks per company document:")
    company_counts = {}
    for chunk in all_chunks:
        if chunk["doc_type"] == "company":
            company_counts[chunk["theme"]] = company_counts.get(chunk["theme"], 0) + 1
    for theme, count in sorted(company_counts.items()):
        print(f"  {theme}: {count}")


if __name__ == "__main__":
    main()
