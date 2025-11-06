# app.py
import streamlit as st
import requests
import uuid

# -----------------------------
# Backend endpoint (fixed)
# -----------------------------
BACKEND_URL = "http://127.0.0.1:8006/chat"   # change only if your port/path differs

st.set_page_config(page_title="SAP AI Assistant", page_icon="💬", layout="wide")

# -----------------------------
# Minimal modern styling
# -----------------------------
st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 960px; margin: auto;}
.msg-row {display:flex; gap:.5rem; margin:.6rem 0;}
.msg-row.user {justify-content:flex-end;}
.msg-row.bot {justify-content:flex-start;}
.bubble {padding:.75rem 1rem; border-radius:1rem; max-width:78%; line-height:1.45; font-size:.95rem; box-shadow:0 1px 2px rgba(0,0,0,.06);}
.bubble.user {background:#1e3a8a; color:#fff; border-bottom-right-radius:.35rem;}
.bubble.bot {background:#f5f5f7; color:#111; border-bottom-left-radius:.35rem; border:1px solid #e9e9ee;}
.quick-replies {display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.35rem;}
.quick-replies button {border-radius:999px; padding:.25rem .7rem; border:1px solid #ddd; background:#fafafa;}
.stChatInput {position:sticky; bottom:0; background:#fff;}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Session state
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []        # [{"role": "user"/"bot", "content": str, "choices": list|None}]
if "backend_state" not in st.session_state:
    st.session_state.backend_state = {}   # last state from backend
if "pending_input" not in st.session_state:
    st.session_state.pending_input = ""   # quick-reply injection

# -----------------------------
# Backend call
# -----------------------------
def call_backend(user_text: str, state: dict):
    payload = {"user": user_text, "state": state or {}}
    try:
        resp = requests.post(BACKEND_URL, json=payload, timeout=90)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"reply": f"❌ Backend error: {e}", "state": state or {}}

# -----------------------------
# Render a single message
# -----------------------------
def render_message(role: str, content: str, choices=None):
    is_user = role == "user"
    row_cls = "user" if is_user else "bot"
    bub_cls = "bubble user" if is_user else "bubble bot"

    st.markdown(
        f"""
        <div class="msg-row {row_cls}">
            <div class="{bub_cls}">{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Quick replies from backend state. Use unique keys to avoid duplicates.
    if (not is_user) and choices:
        st.markdown('<div class="quick-replies">', unsafe_allow_html=True)
        for choice in choices:
            if st.button(choice, key=f"qr_{uuid.uuid4()}"):
                st.session_state.pending_input = choice
        st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# Header
# -----------------------------
left, right = st.columns([0.82, 0.18])
with left:
    st.markdown("### SAP AI Assistant")
    st.caption("Chat UI that mirrors backend replies and carries backend state automatically.")
with right:
    if st.button("Reset"):
        st.session_state.clear()
        st.rerun()

st.divider()

# -----------------------------
# History
# -----------------------------
for m in st.session_state.messages:
    render_message(m["role"], m["content"], m.get("choices"))

# -----------------------------
# Input
# -----------------------------
user_input = st.chat_input("Type your message...")

# If a quick-reply was clicked, use it as the next input
if st.session_state.pending_input:
    user_input = st.session_state.pending_input
    st.session_state.pending_input = ""

# -----------------------------
# Send & handle response
# -----------------------------
if user_input:
    # show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    render_message("user", user_input)

    # call backend with previous state
    result = call_backend(user_input, st.session_state.get("backend_state", {}))

    # store new state exactly as received
    reply = result.get("reply", "")
    new_state = result.get("state", {}) or {}
    st.session_state.backend_state = new_state

    # surface choices if provided by backend
    choices = new_state.get("choices") if isinstance(new_state, dict) else None

    # show bot message
    st.session_state.messages.append({"role": "bot", "content": reply, "choices": choices})
    render_message("bot", reply, choices)

    # optional: inspect backend state
    with st.expander("Backend State", expanded=False):
        st.json(new_state)

    st.rerun()
