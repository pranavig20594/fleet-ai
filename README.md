# FleetAI — Fleet Document Intelligence

## What is this?

Imagine you run a trucking company with 6 trucks. Each truck generates a pile of paperwork every month — fuel receipts, maintenance invoices, registration certificates, tax forms. These come in as PDFs, printed receipts, and emails from repair shops.

FleetAI lets you **ask plain English questions** about all of that paperwork and get instant answers:

> "Which truck cost the most to maintain this year?"
> "Find the tax form for truck 84"
> "How much did we spend on fuel in March?"

Instead of digging through folders or spreadsheets, you just ask — like texting a colleague who has read every document.

---

## How does it work? (Simple version)

```
Your documents (PDFs + emails)
        ↓
  FleetAI reads them all
        ↓
  AI extracts key info (truck #, date, amount, type)
        ↓
  Everything stored in a searchable database
        ↓
  You ask a question in the chat
        ↓
  AI figures out what to look up
        ↓
  You get an answer with sources cited
```

---

## What you need before starting

| Requirement | Why |
|---|---|
| Python 3.9+ | The programming language the app runs on |
| OpenRouter API key | The AI service that reads and understands documents (free to sign up) |
| ~500MB disk space | For the document database |

---

## Setup (one time only)

### Step 1 — Get the code ready

Open your terminal and navigate to the project folder:
```bash
cd ~/fleet-ai
```

Create a virtual environment (an isolated Python workspace):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install all required packages:
```bash
pip install -r requirements.txt
```

---

### Step 2 — Add your API key

Get a free API key from **openrouter.ai** (sign up → Keys → Create Key).

Open the `.env` file in the project folder and paste your key:
```
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL=deepseek/deepseek-chat
```

---

### Step 3 — Generate test documents

This creates 119 realistic (but fake) fleet documents — fuel receipts as PDFs, maintenance invoices as emails, registration certificates, tax forms, and titles:
```bash
python synthetic_data/generate.py
```

You'll see: `Generated 119 documents → /fleet-ai/documents`

---

### Step 4 — Ingest the documents

This is the one-time setup step where the AI reads every document and extracts key information. It takes about 7–8 minutes because the AI processes one document at a time to stay within free tier limits:

```bash
python ingest.py
```

You'll see each document being processed:
```
ok  fuel_receipt           truck=84   fuel_84_0.pdf
ok  maintenance_receipt    truck=31   maint_31_44.eml
...
Done — 119 documents, 6 trucks
```

---

### Step 5 — Launch the app

```bash
streamlit run app.py
```

Open your browser and go to: **http://localhost:8501**

---

## Using the app

The sidebar has example questions to get you started. You can also type anything in the chat box.

**Example questions:**
- `Which truck had the highest maintenance costs?`
- `How much did we spend on fuel last quarter?`
- `Find the tax form for truck 84`
- `Show me all documents for truck 31`
- `What does truck 22 need for its registration renewal?`
- `List all maintenance from Peterbilt of Dallas`
- `Which drivers have the most fuel receipts?`
- `How much did we spend on parts in May 2024?`

---

## Adding your own real documents

To use FleetAI with your actual documents instead of the test data:

1. Drop your PDF files and `.eml` email files into the `documents/` folder
2. Run `python ingest.py` — it will only process new files (skips duplicates)
3. Refresh the app

Supported file types: **PDF**, **email (.eml)**, **plain text (.txt)**, **images (.png, .jpg)**

---

## Project files explained

```
fleet-ai/
├── app.py                  ← The chat interface (what you see in the browser)
├── agent.py                ← The AI brain (decides what to look up and how to answer)
├── ingest.py               ← Reads documents and builds the database
├── schema.sql              ← Database structure definition
├── requirements.txt        ← List of Python packages needed
├── .env                    ← Your API key (never share this file)
├── fleet.db                ← SQLite database (created after ingest)
├── chroma_db/              ← Vector search index (created after ingest)
├── documents/              ← Your fleet documents go here
├── synthetic_data/
│   └── generate.py         ← Generates fake test documents
└── tools/
    ├── sql_tool.py         ← Searches the structured database
    └── search_tool.py      ← Searches document text by meaning
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Missing API key` error | Check your `.env` file has the correct key |
| `429 rate limited` during ingest | Wait a few minutes and re-run `python ingest.py` (it skips already-processed files) |
| All documents show as `other` with no truck | Your API key wasn't set during ingest — wipe and re-run: `rm fleet.db chroma_db/chroma.sqlite3 && python ingest.py` |
| App won't start | Make sure you ran `source .venv/bin/activate` first |
