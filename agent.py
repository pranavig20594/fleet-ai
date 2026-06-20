"""
FleetAI agent: hybrid SQL + vector-search over fleet documents.
"""
from __future__ import annotations
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
from tools.sql_tool    import query_database
from tools.search_tool import search_documents, get_document

MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")

SYSTEM_PROMPT = """You are FleetAI, an assistant for trucking fleet operators.
You answer questions about trucks, drivers, documents, costs, and compliance.

RULES — follow these strictly:
1. Always use tools before answering. Never answer fleet questions from memory.
2. Ground every claim in what the tools return. If tools return nothing, say so explicitly.
3. Always cite sources: document ID, type, date, truck number.
4. For financial questions, show the SQL that produced the numbers.
5. Never guess or infer document contents beyond what the tools return.
6. When a question needs both a database count and document detail, call both tools.

TOOL SELECTION GUIDE:
- Totals, counts, trends, comparisons, date ranges → query_database
- Find a specific document, text search, "show me the..." → search_documents
- Read the full text of one document you already identified → get_document
- Complex questions (e.g. "what's left to renew for truck 84?") → use both"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "Run a natural-language question against the structured fleet database "
                "(trucks, drivers, documents). Best for: totals, counts, averages, date "
                "ranges, comparisons, 'how much', 'which truck', 'how many'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to answer via SQL"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Semantic search over document text. Best for: finding a specific form, "
                "looking up document content, 'show me the tax form for truck 84', "
                "'find receipts mentioning brakes'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":        {"type": "string",  "description": "What to search for"},
                    "truck_number": {"type": "string",  "description": "Optional: filter to one truck"},
                    "n_results":    {"type": "integer", "description": "Results to return (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document",
            "description": "Fetch the full text and metadata of one document by its numeric ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "integer", "description": "The document ID"},
                },
                "required": ["doc_id"],
            },
        },
    },
]


def _run_tool(client: OpenAI, name: str, inp: dict) -> str:
    if name == "query_database":
        result = query_database(client, inp["question"])
    elif name == "search_documents":
        result = search_documents(inp["query"], inp.get("n_results", 5), inp.get("truck_number"))
    elif name == "get_document":
        result = get_document(inp["doc_id"])
    else:
        result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result, indent=2, default=str)


def ask(question: str, history: list | None = None) -> tuple[str, list]:
    """Returns (answer_text, updated_history)."""
    client   = OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
    messages = (history or []) + [{"role": "user", "content": question}]

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content, messages

        for tool_call in msg.tool_calls:
            result = _run_tool(client, tool_call.function.name, json.loads(tool_call.function.arguments))
            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      result,
            })


# ---------------------------------------------------------------------------
# CLI mode
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("FleetAI  —  type 'quit' to exit\n")
    history: list = []
    while True:
        q = input("You: ").strip()
        if not q or q.lower() in ("quit", "exit"):
            break
        answer, history = ask(q, history)
        print(f"\nFleetAI: {answer}\n")
