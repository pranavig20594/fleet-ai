from __future__ import annotations

import sqlite3
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = "./chroma_db"
DB_PATH = "fleet.db"


def _collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection("fleet_docs", embedding_function=ef)


def search_documents(query: str, n_results: int = 5, truck_number: str = None) -> list[dict]:
    col = _collection()
    where = {"truck_number": truck_number} if truck_number else None
    res = col.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for chunk, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        hits.append({
            "chunk":         chunk,
            "doc_id":        meta.get("doc_id"),
            "doc_type":      meta.get("doc_type"),
            "truck_number":  meta.get("truck_number"),
            "date":          meta.get("date"),
            "file_path":     meta.get("file_path"),
            "relevance":     round(1 - dist, 3),
        })
    return hits


def get_document(doc_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT d.*, t.number AS truck_number, dr.name AS driver_name
            FROM documents d
            LEFT JOIN trucks  t  ON d.truck_id  = t.id
            LEFT JOIN drivers dr ON d.driver_id = dr.id
            WHERE d.id = ?
            """,
            (doc_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
