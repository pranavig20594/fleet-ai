# FleetAI — Architecture

## System Overview

FleetAI has two phases: a **one-time setup** (ingestion) and the **live chat** (query).

---

## Phase 1 — Ingestion (Run once)

This is how raw documents get turned into a searchable database.

```
┌─────────────────────────────────────────────────────────────┐
│                     documents/ folder                        │
│                                                             │
│   fuel_84_0.pdf    maint_31.eml    reg_22.pdf   tax_09.pdf │
│   (fuel receipt)   (shop email)    (registration) (IRS form)│
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │       ingest.py        │
              │                        │
              │  1. Read file          │
              │     PDF → pdfplumber   │
              │     EML → email lib    │
              │     IMG → tesseract    │
              └────────────┬───────────┘
                           │  raw text
                           ▼
              ┌────────────────────────┐
              │    AI Extraction       │
              │  (OpenRouter LLM)      │
              │                        │
              │  "What truck is this?  │
              │   What type of doc?    │
              │   What's the amount?   │
              │   What's the date?"    │
              └────────┬───────────────┘
                       │
           ┌───────────┴────────────┐
           │                        │
           ▼                        ▼
┌──────────────────┐    ┌──────────────────────┐
│    fleet.db      │    │     chroma_db/        │
│  (SQLite)        │    │  (Vector Search)      │
│                  │    │                       │
│  trucks table    │    │  Document chunks      │
│  drivers table   │    │  stored as            │
│  documents table │    │  meaning-vectors      │
│                  │    │  for fuzzy search     │
│  Structured:     │    │                       │
│  amounts, dates, │    │  "Find receipts       │
│  truck IDs, types│    │   mentioning brakes"  │
└──────────────────┘    └──────────────────────┘
```

---

## Phase 2 — Query (Every chat message)

This is what happens every time you ask a question.

```
┌─────────────────────────────────┐
│         User (browser)          │
│                                 │
│  "Which truck cost the most     │
│   to maintain this year?"       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│           app.py                │
│       (Streamlit UI)            │
│                                 │
│  Displays chat bubbles          │
│  Stores conversation history    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                        agent.py                              │
│                    (The AI Brain)                            │
│                                                             │
│  System prompt: "You are FleetAI. Always use tools         │
│  before answering. Cite your sources."                      │
│                                                             │
│  AI reads the question and decides:                         │
│  "I need to query the database for cost totals"             │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │  Which tool do I need?  │
          └────────────┬────────────┘
                       │
         ┌─────────────┼──────────────┐
         │             │              │
         ▼             ▼              ▼
 ┌──────────────┐ ┌──────────┐ ┌──────────────┐
 │ query_       │ │ search_  │ │ get_         │
 │ database     │ │ documents│ │ document     │
 │              │ │          │ │              │
 │ "How much    │ │ "Find    │ │ "Get full    │
 │  per truck?" │ │  the tax │ │  text of     │
 │              │ │  form"   │ │  doc #42"    │
 └──────┬───────┘ └────┬─────┘ └──────┬───────┘
        │              │               │
        ▼              ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ sql_tool.py  │ │search_tool.py│ │search_tool.py│
│              │ │              │ │              │
│ AI writes SQL│ │ Converts     │ │ Looks up row │
│ Runs against │ │ question to  │ │ in fleet.db  │
│ fleet.db     │ │ vector,      │ │ by ID        │
│              │ │ searches     │ │              │
│ Returns rows │ │ chroma_db    │ │ Returns full │
│ + SQL shown  │ │              │ │ document     │
└──────┬───────┘ └────┬─────────┘ └──────┬───────┘
        │              │               │
        └──────────────┴───────────────┘
                       │
                       │  tool results
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                        agent.py                              │
│                                                             │
│  AI reads tool results and writes a final answer:           │
│                                                             │
│  "Truck 31 had the highest maintenance costs at $4,821.     │
│   Sources: doc #44 (2024-03-12), doc #46 (2024-07-08),     │
│   doc #47 (2024-09-22) — all from Peterbilt of Dallas."    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────┐
│         User (browser)          │
│                                 │
│  Sees the answer in the chat    │
└─────────────────────────────────┘
```

---

## Data Flow Summary

```
documents/        →  ingest.py  →  fleet.db + chroma_db
(PDFs, emails)       (one time)     (permanent storage)

User question     →  agent.py   →  sql_tool / search_tool  →  Answer
(every message)      (AI brain)     (database lookups)
```

---

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Chat UI | Streamlit | Web interface in Python |
| AI Agent | OpenRouter (DeepSeek) | Understands questions, picks tools, writes answers |
| SQL generation | OpenRouter (DeepSeek) | Translates English → SQL |
| Structured storage | SQLite (`fleet.db`) | Stores truck/driver/document records |
| Semantic search | ChromaDB | Finds documents by meaning, not just keywords |
| PDF reading | pdfplumber | Extracts text from PDF files |
| Email reading | Python `email` stdlib | Parses `.eml` email files |
| PDF generation | fpdf2 | Creates synthetic test PDFs |
| Test data | `generate.py` | Creates realistic messy fake documents |

---

## Why two databases?

**SQLite** (`fleet.db`) is like a spreadsheet — great for exact lookups:
- "Total fuel spend in Q1" → SQL query, fast and precise

**ChromaDB** (`chroma_db/`) is like a smart search engine — great for fuzzy meaning:
- "Find receipts that mention brake issues" → vector similarity search

Most questions use both together for the best answer.
