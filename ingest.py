"""
Ingest fleet documents into SQLite + ChromaDB.
Usage: python ingest.py [docs_dir]   (default: ./documents)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
import chromadb
import pdfplumber
from chromadb.utils import embedding_functions

DB_PATH = "fleet.db"
CHROMA_PATH = "./chroma_db"

try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

EXTRACTION_PROMPT = """Extract structured information from this fleet document. Return ONLY valid JSON — no explanation, no markdown.

Document text:
{text}

Return this exact JSON shape (use null for any field not found):
{{
  "doc_type":     "one of: fuel_receipt | title | tax_form | maintenance_receipt | registration | insurance | inspection | weigh_ticket | bill_of_lading | other",
  "truck_number": "truck unit number as a string, e.g. '84' or '115'",
  "driver_name":  "full driver name if present",
  "trailer_number":"trailer unit number if present",
  "date":         "YYYY-MM-DD",
  "amount":       "numeric dollar amount without $ sign, e.g. 532.10",
  "vendor":       "company or person who issued or received payment",
  "description":  "one-sentence summary of what this document is"
}}"""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def init_db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def _get_or_insert(conn, table: str, key_col: str, key_val: str, extra: dict = None) -> int | None:
    if not key_val:
        return None
    import sqlite3
    row = conn.execute(f"SELECT id FROM {table} WHERE {key_col} = ?", (key_val,)).fetchone()
    if row:
        return row[0]
    cols = [key_col] + list((extra or {}).keys())
    vals = [key_val] + list((extra or {}).values())
    conn.execute(
        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(['?']*len(vals))})",
        vals,
    )
    conn.commit()
    return conn.execute(f"SELECT id FROM {table} WHERE {key_col} = ?", (key_val,)).fetchone()[0]


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(path: str) -> str:
    import email as email_lib
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    elif ext == ".eml":
        msg = email_lib.message_from_string(p.read_text(errors="replace"))
        parts = [
            f"From: {msg.get('From', '')}",
            f"Subject: {msg.get('Subject', '')}",
            f"Date: {msg.get('Date', '')}",
            "",
        ]
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    parts.append(part.get_payload(decode=True).decode(errors="replace"))
        else:
            payload = msg.get_payload(decode=True)
            parts.append(payload.decode(errors="replace") if payload else msg.get_payload())
        return "\n".join(parts)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        if HAS_OCR:
            return pytesseract.image_to_string(Image.open(path))
        return ""
    elif ext == ".txt":
        return p.read_text(errors="replace")
    return ""


def chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i : i + size])
        if chunk:
            chunks.append(chunk)
    return chunks or [text]


# ---------------------------------------------------------------------------
# Extraction via Claude
# ---------------------------------------------------------------------------

def extract_fields(client: OpenAI, text: str) -> dict:
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat"),
                messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:4000])}],
                max_tokens=512,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            if "429" in str(e) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f"  rate limited — waiting {wait}s …")
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Ingest a single file
# ---------------------------------------------------------------------------

def ingest_file(path: str, client: OpenAI, collection, conn):
    import sqlite3

    file_hash = hashlib.md5(Path(path).read_bytes()).hexdigest()
    if conn.execute("SELECT 1 FROM documents WHERE file_hash = ?", (file_hash,)).fetchone():
        print(f"  skip (duplicate): {Path(path).name}")
        return

    text = extract_text(path)
    if not text.strip():
        print(f"  skip (no text):   {Path(path).name}")
        return

    try:
        fields = extract_fields(client, text)
    except Exception as e:
        print(f"  warn (extract failed, storing raw): {e}")
        fields = {}

    truck_id  = _get_or_insert(conn, "trucks",  "number", fields.get("truck_number"))
    driver_id = _get_or_insert(conn, "drivers", "name",   fields.get("driver_name"),
                                extra={"truck_id": truck_id} if truck_id else None)

    conn.execute(
        """INSERT INTO documents
           (type, truck_id, driver_id, date, amount, vendor, description, file_path, raw_text, file_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            fields.get("doc_type", "other"),
            truck_id,
            driver_id,
            fields.get("date"),
            fields.get("amount"),
            fields.get("vendor"),
            fields.get("description"),
            path,
            text,
            file_hash,
        ),
    )
    conn.commit()
    doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    chunks = chunk_text(text)
    if chunks:
        collection.add(
            documents=chunks,
            metadatas=[{
                "doc_id":       doc_id,
                "doc_type":     fields.get("doc_type", "other"),
                "truck_number": fields.get("truck_number") or "",
                "date":         fields.get("date") or "",
                "file_path":    path,
            }] * len(chunks),
            ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        )

    print(f"  ok  {fields.get('doc_type','other'):<22} truck={fields.get('truck_number') or '?':<5} {Path(path).name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(docs_dir: str = "./documents"):
    client = OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
    conn   = init_db()

    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    ef     = embedding_functions.DefaultEmbeddingFunction()
    col    = chroma.get_or_create_collection("fleet_docs", embedding_function=ef)

    files = [
        f for f in Path(docs_dir).rglob("*")
        if f.suffix.lower() in (".pdf", ".eml", ".txt", ".png", ".jpg", ".jpeg")
    ]
    print(f"Found {len(files)} files in {docs_dir}\n")

    for f in files:
        try:
            ingest_file(str(f), client, col, conn)
        except Exception as e:
            print(f"  error {f.name}: {e}")
        time.sleep(4)  # stay under 15 req/min free tier limit

    import sqlite3
    print(f"\nDone — {conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]} documents, "
          f"{conn.execute('SELECT COUNT(*) FROM trucks').fetchone()[0]} trucks")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "./documents")
