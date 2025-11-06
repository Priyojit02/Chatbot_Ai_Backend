import streamlit as st
import requests
import json
import uuid

# ---------------------------------------
# Backend Configuration
# ---------------------------------------
BACKEND_URL = "http://127.0.0.1:8004/chat"  # Your FastAPI /chat endpoint

st.set_page_config(page_title="SAP AI Chat Assistant", page_icon="💬", layout="wide")

# ---------------------------------------
# Custom Styling
# ---------------------------------------
st.markdown("""
<style>
/* Layout */
.block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 900px; margin: auto;}

/* Chat bubbles */
.chat-bubble {
    padding: 0.7rem 1rem;
    border-radius: 1rem;
    max-width: 75%;
    word-wrap: break-word;
    font-size: 0.95rem;
    line-height: 1.4;
}
.chat-user {
    background-color: #dcf8c6; /* WhatsApp green bubble */
    margin-left: auto;
    border-bottom-right-radius: 0.3rem;
}
.chat-bot {
    background-color: #ffffff;
    border: 1px solid #e5e5e5;
    border-bottom-left-radius: 0.3rem;
}

/* Message container */
.msg-row {
    display: flex;
    align-items: flex-start;
    margin-bottom: 0.8rem;
}
.msg-row.user { justify-content: flex-end; }
.msg-row.bot { justify-content: flex-start; }

/* Avatar */
.avatar {
    width: 35px; height: 35px;
    border-radius: 50%;
    font-weight: bold;
    display: flex; align-items: center; justify-content: center;
    color: white; margin: 0 0.5rem;
}
.avatar.user { background-color: #075e54; order: 2; }
.avatar.bot { background-color: #25d366; order: 1; }

/* Quick replies */
.quick-replies { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
.quick-replies button {
    border-radius: 1rem; border: 1px solid #ccc; padding: 0.3rem 0.7rem;
    background: #f0f0f0; color: #333; cursor: pointer;
}

/* Chat input box (sticky) */
.stChatInput { position: sticky; bottom: 0; background-color: white; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------
# Session State Initialization
# ---------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{"role": "user"/"bot", "content": str}]
if "backend_state" not in st.session_state:
    st.session_state.backend_state = {}
if "pending_input" not in st.session_state:
    st.session_state.pending_input = ""

# ---------------------------------------
# Helper: Call backend API
# ---------------------------------------
def call_backend(user_text, state):
    """Send message + previous state to backend and return reply + state."""
    try:
        payload = {"user": user_text, "state": state or {}}
        response = requests.post(BACKEND_URL, json=payload, timeout=90)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"reply": f"❌ Backend error: {e}", "state": state or {}}

# ---------------------------------------
# Helper: Render messages
# ---------------------------------------
def render_message(role, content, choices=None):
    """Render chat bubble for user or bot."""
    is_user = role == "user"
    msg_class = "user" if is_user else "bot"
    bubble_class = "chat-bubble chat-user" if is_user else "chat-bubble chat-bot"
    avatar_class = "avatar user" if is_user else "avatar bot"
    avatar_text = "U" if is_user else "🤖"

    # Message row
    st.markdown(
        f"""
        <div class="msg-row {msg_class}">
            <div class="{avatar_class}">{avatar_text}</div>
            <div class="{bubble_class}">{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render quick reply buttons (if backend provides them)
    if not is_user and choices:
        with st.container():
            st.markdown('<div class="quick-replies">', unsafe_allow_html=True)
            for choice in choices:
                unique_key = str(uuid.uuid4())
                if st.button(choice, key=unique_key):
                    st.session_state.pending_input = choice
            st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------
# Header
# ---------------------------------------
col1, col2 = st.columns([0.8, 0.2])
with col1:
    st.markdown("### 💬 SAP AI Address Assistant")
    st.caption("Chat with your backend — fully context-aware (WhatsApp-style UI).")
with col2:
    if st.button("🔄 Reset Chat"):
        st.session_state.clear()
        st.rerun()

st.divider()

# ---------------------------------------
# Show message history
# ---------------------------------------
for msg in st.session_state.messages:
    render_message(msg["role"], msg["content"], msg.get("choices"))

# ---------------------------------------
# Chat input area
# ---------------------------------------
user_input = st.chat_input("Type your message...")

# Handle quick-reply selection
if st.session_state.pending_input:
    user_input = st.session_state.pending_input
    st.session_state.pending_input = ""

# ---------------------------------------
# Send new message
# ---------------------------------------
if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    render_message("user", user_input)

    # Call backend with previous state
    result = call_backend(user_input, st.session_state.get("backend_state", {}))

    # Extract backend reply + new state
    reply = result.get("reply", "")
    new_state = result.get("state", {}) or {}

    # Save new state for next turn
    st.session_state.backend_state = new_state

    # Save & display bot reply
    choices = None
    if isinstance(new_state, dict):
        choices = new_state.get("choices")

    st.session_state.messages.append({
        "role": "bot",
        "content": reply,
        "choices": choices
    })
    render_message("bot", reply, choices)

    # Optional: show the backend state JSON for debugging (can hide later)
    with st.expander("📦 Backend State", expanded=False):
        st.json(new_state)

    st.rerun()
