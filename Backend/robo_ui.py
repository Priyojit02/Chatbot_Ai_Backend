# app.py
import requests
import streamlit as st

# -----------------------------
# BASIC CONFIG
# -----------------------------
BACKEND_URL = "http://127.0.0.1:8004/chat"   # your FastAPI backend endpoint

st.set_page_config(
    page_title="SAP AI Address Assistant",
    page_icon="🤖",
    layout="wide",
)

# -----------------------------
# CUSTOM STYLING
# -----------------------------
CUSTOM_CSS = '''
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
.chat-bubble {padding: 0.7rem 0.9rem; border-radius: 1.2rem; max-width: 72%;
              word-wrap: break-word; line-height: 1.35; font-size: 0.95rem;}
.chat-left  {background: rgba(0,0,0,0.06); color: #111; border-top-left-radius: 0.4rem;}
.chat-right {background: #155E75; color: #fff; border-top-right-radius: 0.4rem; margin-left: auto;}
.avatar {width: 36px; height: 36px; border-radius: 50%; display: inline-flex;
         align-items: center; justify-content: center; margin-right: 0.5rem;
         background: #0ea5e9; color: white; font-weight: 700;}
.avatar.user {background: #155E75;}
.avatar.bot {background: #111827;}
.row {display: flex; gap: 0.6rem; margin: 0.25rem 0 0.6rem 0; align-items: flex-start;}
.row.right {justify-content: flex-end;}
.row.right .avatar {order: 2; margin-right: 0; margin-left: 0.5rem;}
.row.right .bubble-wrap {order: 1; justify-content: flex-end;}
.quick-replies {display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.4rem;}
.quick-replies button {border-radius: 999px; padding: 0.25rem 0.7rem; border: 1px solid rgba(0,0,0,0.15);}
.stChatInput {position: sticky; bottom: 0; background: white;}
</style>
'''
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------
# SESSION STATE
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []   # [{"role": "user"/"assistant", "content": "...", "choices": [...] }]
if "backend_state" not in st.session_state:
    st.session_state.backend_state = {}
if "pending_input" not in st.session_state:
    st.session_state.pending_input = ""

# -----------------------------
# HELPERS
# -----------------------------
def post_to_backend(user_text: str, state: dict):
    """Send the message and state to FastAPI backend and return response."""
    payload = {"user": user_text, "state": state or {}}
    try:
        resp = requests.post(BACKEND_URL, json=payload, timeout=90)
        if resp.status_code >= 400:
            return {"error": f"{resp.status_code}: {resp.text}"}
        data = resp.json()
        return {"reply": data.get("reply", ""), "state": data.get("state", {})}
    except requests.RequestException as e:
        return {"error": str(e)}

def render_message(role: str, content: str, choices=None):
    """Display user or assistant message with style and optional choices."""
    is_user = role == "user"
    row_class = "row right" if is_user else "row"
    avatar_class = "avatar user" if is_user else "avatar bot"
    avatar_text = "U" if is_user else "🤖"
    bubble_class = "chat-bubble chat-right" if is_user else "chat-bubble chat-left"

    st.markdown(
        f'''
        <div class="{row_class}">
            <div class="{avatar_class}">{avatar_text}</div>
            <div class="bubble-wrap">
                <div class="{bubble_class}">{content}</div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True
    )

    # Quick replies (from backend state["choices"])
    if (not is_user) and choices:
        st.markdown('<div class="quick-replies">', unsafe_allow_html=True)
        for i, choice in enumerate(choices):
            if st.button(choice, key=f"qr_{len(st.session_state.messages)}_{i}"):
                st.session_state.pending_input = choice
        st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# HEADER
# -----------------------------
left, right = st.columns([0.72, 0.28])
with left:
    st.title("SAP AI Address Assistant")
    st.caption("Conversational frontend with backend state flow.")
with right:
    if st.button("Reset chat"):
        st.session_state.clear()
        st.rerun()

# -----------------------------
# CHAT HISTORY
# -----------------------------
for m in st.session_state.messages:
    render_message(m["role"], m["content"], m.get("choices"))

# -----------------------------
# USER INPUT
# -----------------------------
user_text = st.chat_input("Type your message…")

# If a quick-reply was clicked
if st.session_state.pending_input:
    user_text = st.session_state.pending_input
    st.session_state.pending_input = ""

if user_text:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_text})
    render_message("user", user_text)

    # Send to backend with previous state (context)
    result = post_to_backend(user_text, st.session_state.get("backend_state", {}))

    if "error" in result:
        bot_text = f"❌ Backend error: {result['error']}"
        st.session_state.messages.append({"role": "assistant", "content": bot_text})
        render_message("assistant", bot_text)
    else:
        bot_text = result.get("reply", "")
        new_state = result.get("state", {}) or {}
        st.session_state.backend_state = new_state

        # Extract quick choices if available
        choices = new_state.get("choices") if isinstance(new_state, dict) else None
        st.session_state.messages.append({"role": "assistant", "content": bot_text, "choices": choices})
        render_message("assistant", bot_text, choices=choices)
