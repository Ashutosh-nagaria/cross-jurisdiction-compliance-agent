"""
Chapter 4: creates the Atlas Vector Search index on compliance_chunks.

This does not need to run every time, only once (or again if the index
gets deleted). It must run after ingest.py has put at least one document
with an embedding into the collection.

A vector index is what lets MongoDB search by meaning instead of by
matching exact words: it lets the database quickly find which stored
chunks have embeddings (the number-lists produced by Voyage AI) that are
mathematically closest to a new question's embedding, without comparing
against every single chunk one by one.
"""

import os
import time

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()
MONGODB_URI = os.environ["MONGODB_URI"]

DATABASE_NAME = "compliance_agent"
COLLECTION_NAME = "compliance_chunks"
INDEX_NAME = "compliance_chunks_vector_index"
EMBEDDING_DIMENSION = 1024  # voyage-law-2's embedding size, must match ingest.py


def main():
    client = MongoClient(MONGODB_URI)
    collection = client[DATABASE_NAME][COLLECTION_NAME]

    existing_names = {idx["name"] for idx in collection.list_search_indexes()}
    if INDEX_NAME in existing_names:
        print(f"Index '{INDEX_NAME}' already exists, nothing to do.")
        return

    # "vector" tells Atlas the embedding field should be searched by
    # closeness in meaning. The "filter" fields let later searches be
    # narrowed down, for example "only search within eu-gdpr documents",
    # without that narrowing being slow.
    index_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIMENSION,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "doc_type"},
                {"type": "filter", "path": "jurisdiction"},
                {"type": "filter", "path": "theme"},
            ]
        },
        name=INDEX_NAME,
        type="vectorSearch",
    )

    collection.create_search_index(model=index_model)
    print(f"Requested creation of index '{INDEX_NAME}'.")

    # Atlas builds the index in the background, this is not instant, so
    # we check every few seconds until it reports itself ready.
    print("Waiting for the index to finish building...")
    while True:
        indexes = list(collection.list_search_indexes(INDEX_NAME))
        if indexes and indexes[0].get("queryable"):
            print("Index is ready.")
            break
        time.sleep(5)


if __name__ == "__main__":
    main()
