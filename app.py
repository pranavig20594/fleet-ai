"""
FleetAI — Streamlit chat UI
Run: streamlit run app.py
"""
import streamlit as st
from agent import ask

st.set_page_config(page_title="FleetAI", page_icon="🚛", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🚛 FleetAI")
    st.caption("Fleet document intelligence")
    st.divider()

    st.subheader("Try asking:")
    EXAMPLES = [
        "Which truck had the highest maintenance costs?",
        "How much did we spend on fuel last quarter?",
        "Find the tax form for truck 84",
        "Show me all documents for truck 31",
        "What does truck 22 need for its registration renewal?",
        "List all maintenance from Peterbilt of Dallas",
        "Which drivers have the most fuel receipts?",
        "How much did we spend on parts in May 2024?",
    ]
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True, type="secondary"):
            st.session_state["_pending"] = ex

    st.divider()
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history  = []
        st.rerun()

# ---------------------------------------------------------------------------
# State init
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

# ---------------------------------------------------------------------------
# Chat display
# ---------------------------------------------------------------------------
st.title("Fleet Document Intelligence")
st.caption("Ask anything about your trucks, drivers, costs, and documents.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Input (text box or sidebar button)
# ---------------------------------------------------------------------------
question = st.chat_input("Ask about your fleet…")
if "_pending" in st.session_state:
    question = st.session_state.pop("_pending")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching fleet records…"):
            try:
                answer, st.session_state.history = ask(question, st.session_state.history)
            except Exception as e:
                answer = f"Error: {e}"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()
