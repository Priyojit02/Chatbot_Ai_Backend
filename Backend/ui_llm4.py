import streamlit as st
import requests
import html

# ---------------------------------------
# Backend Configuration
# ---------------------------------------
BACKEND_URL = "http://127.0.0.1:8006/chat"  # Your FastAPI /chat endpoint

st.set_page_config(page_title="SAP AI Address Assistant", page_icon="💬", layout="wide")

# ---------------------------------------
# Custom Styling
# ---------------------------------------
st.markdown("""
<style>
/* Layout */
.block-container {padding-top: .5rem; padding-bottom: 2rem; max-width: 900px; margin: auto;}

/* Title bar */
.title-bar {
  display:flex; align-items:baseline; justify-content:space-between; gap:1rem;
  margin: .25rem 0 1rem 0;
}
.title-bar h1 { margin:0; font-size: 22px; font-weight: 700; }
.title-sub { color:#6b7280; font-size: 13px; }

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

# Small helper to safely show text inside bubbles (preserve newlines)
def safe_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")

# ---------------------------------------
# Helper: Render messages
# ---------------------------------------
def render_message(role, content):
    """Render chat bubble for user or bot."""
    is_user = role == "user"
    msg_class = "user" if is_user else "bot"
    bubble_class = "chat-bubble chat-user" if is_user else "chat-bubble chat-bot"
    avatar_class = "avatar user" if is_user else "avatar bot"
    avatar_text = "U" if is_user else "🤖"

    st.markdown(
        f"""
        <div class="msg-row {msg_class}">
            <div class="{avatar_class}">{avatar_text}</div>
            <div class="{bubble_class}">{safe_html(content)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------
# Header (clean + aligned)
# ---------------------------------------
left, right = st.columns([0.85, 0.15])
with left:
    st.markdown("""
    <div class="title-bar">
      <h1>SAP AI Address Assistant</h1>
      <span class="title-sub">Chat with your backend — fully context-aware.</span>
    </div>
    """, unsafe_allow_html=True)
with right:
    if st.button("Reset", use_container_width=True):
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

    # Optional: show the backend state JSON (remove this expander if you don't want it)
    with st.expander("Backend State", expanded=False):
        st.json(new_state)

    st.rerun()
