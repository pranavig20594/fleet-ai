from __future__ import annotations
import os
import re
import sqlite3
from openai import OpenAI

DB_PATH = "fleet.db"

SCHEMA_CONTEXT = """You are a SQLite expert for a trucking fleet database.

Schema:
  trucks(id, number, vin, plate, make, model, year, status)
  drivers(id, name, license_number, truck_id)
  trailers(id, number, plate, truck_id)
  documents(id, type, truck_id, driver_id, trailer_id, date, amount, vendor, description, file_path, ingested_at)

document.type values: fuel_receipt | title | tax_form | maintenance_receipt | registration | insurance | inspection | weigh_ticket | bill_of_lading | other
date is stored as TEXT in YYYY-MM-DD format.
amount is REAL (US dollars).

Write a single SQLite SELECT query to answer this question.
Return ONLY the SQL, no explanation, no markdown fences.

Question: {question}"""


def generate_sql(client: OpenAI, question: str) -> str:
    response = client.chat.completions.create(
        model=os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat"),
        messages=[{"role": "user", "content": SCHEMA_CONTEXT.format(question=question)}],
        max_tokens=512,
    )
    sql = response.choices[0].message.content.strip()
    if "```" in sql:
        m = re.search(r"```(?:sql)?\n?(.*?)```", sql, re.DOTALL)
        if m:
            sql = m.group(1).strip()
    return sql


def run_query(sql: str) -> list[dict]:
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are permitted")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def query_database(client: OpenAI, question: str) -> dict:
    sql = generate_sql(client, question)
    try:
        results = run_query(sql)
        return {"sql": sql, "results": results, "count": len(results)}
    except Exception as e:
        return {"sql": sql, "error": str(e), "results": []}
