import streamlit as st
import requests
import uuid

# ---------------------------------------
# Backend Configuration
# ---------------------------------------
BACKEND_URL = "http://127.0.0.1:8006/chat"  # Your FastAPI /chat endpoint

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
  padding: 0.7rem 1rem; border-radius: 1rem; max-width: 75%;
  word-wrap: break-word; font-size: 0.95rem; line-height: 1.4;
}
.chat-user {
  background-color: #dcdee6; /* neutral user bubble */
  margin-left: auto; border-bottom-right-radius: 0.3rem;
}
.chat-bot {
  background-color: #ffffff; border: 1px solid #e5e5e5;
  border-bottom-left-radius: 0.3rem;
}

/* Message container */
.msg-row { display: flex; align-items: flex-start; margin-bottom: 0.8rem; }
.msg-row.user { justify-content: flex-end; }
.msg-row.bot  { justify-content: flex-start; }

/* Avatar */
.avatar {
  width: 35px; height: 35px; border-radius: 50%; font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  color: white; margin: 0 0.5rem;
}
.avatar.user { background-color: #3b82f6; order: 2; }
.avatar.bot  { background-color: #111827; order: 1; }

/* Sticky input */
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
# Helper: Render messages (no quick-reply bubbles)
# ---------------------------------------
def render_message(role, content):
    """Render chat bubble for user or bot (no quick reply buttons)."""
    is_user = role == "user"
    msg_class = "user" if is_user else "bot"
    bubble_class = "chat-bubble chat-user" if is_user else "chat-bubble chat-bot"
    avatar_class = "avatar user" if is_user else "avatar bot"
    avatar_text = "U" if is_user else "🤖"

    st.markdown(
        f"""
        <div class="msg-row {msg_class}">
            <div class="{avatar_class}">{avatar_text}</div>
            <div class="{bubble_class}">{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------
# Header
# ---------------------------------------
col1, col2 = st.columns([0.8, 0.2])
with col1:
    st.markdown("### 💬 SAP AI Address Assistant")
    st.caption("Chat with your backend — fully context-aware.")
with col2:
    if st.button("🔄 Reset Chat"):
        st.session_state.clear()
        st.rerun()

st.divider()

# ---------------------------------------
# Show message history
# ---------------------------------------
for msg in st.session_state.messages:
    render_message(msg["role"], msg["content"])

# ---------------------------------------
# Chat input area
# ---------------------------------------
user_input = st.chat_input("Type your message...")

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
    st.session_state.messages.append({"role": "bot", "content": reply})
    render_message("bot", reply)

    # Optional: show the backend state JSON for debugging (keep or remove)
    with st.expander("📦 Backend State", expanded=False):
        st.json(new_state)

    st.rerun()
