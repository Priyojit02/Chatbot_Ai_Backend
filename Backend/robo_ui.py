# sap_robo_ui.py
import os
import time
import json
import requests
import streamlit as st

# =========================
# CONFIG
# =========================
DEFAULT_API_URL = os.getenv("SAP_ASSISTANT_API", "http://127.0.0.1:8000/chat")
st.set_page_config(page_title="Robo SAP Assistant", page_icon="🤖", layout="wide")

# =========================
# THEME & STYLES
# =========================
ROBO_CSS = """
<style>
/* Page */
*[data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 800px at 10% 10%, #0d0d16 0%, #07070e 40%, #05050a 100%);
  color: #e6e9ef;
}
*[data-testid="stHeader"] { background: rgba(0,0,0,0); }

/* Robo header */
.robo-header {
  display:flex; align-items:center; gap:16px;
  padding: 18px 22px; border-radius: 16px;
  background: linear-gradient(135deg, rgba(28,28,62,0.8), rgba(14,14,28,0.6));
  border: 1px solid rgba(120, 120, 255, 0.18);
  box-shadow: 0 10px 30px rgba(0,0,0,0.35), inset 0 0 40px rgba(100,100,255,0.06);
}

.robo-face {
  width:56px; height:56px; border-radius:14px;
  background: radial-gradient(120% 120% at 20% 20%, #1f254b, #0f1230);
  border: 1px solid rgba(120, 120, 255, 0.25);
  display:flex; align-items:center; justify-content:center;
  box-shadow: 0 10px 24px rgba(50,60,160,0.25);
  position: relative;
  overflow: hidden;
}
.robo-eye {
  width:10px; height:10px; border-radius:50%;
  background: #71e7ff; box-shadow: 0 0 8px #71e7ff, 0 0 18px #71e7ff80;
  margin: 0 6px;
}
.robo-vis {
  display:flex; align-items:center; gap:6px;
}
.robo-title { font-size: 20px; font-weight: 700; letter-spacing: 0.4px; }
.robo-sub { font-size: 12px; opacity: 0.8; margin-top: 2px; }

/* Chat bubbles */
.chat-wrap { margin-top: 12px; }
.bubble {
  padding: 12px 14px; border-radius: 14px; margin: 8px 0; max-width: 900px;
  border: 1px solid rgba(255,255,255,0.06);
  box-shadow: 0 8px 18px rgba(0,0,0,0.25);
  line-height: 1.45;
}
.user { background: linear-gradient(135deg, #152236, #111827); }
.assistant { background: linear-gradient(135deg, #0d1d2e, #0c1a29); border-color: rgba(100,200,255,0.2); }
.bubble .meta { font-size: 11px; opacity: 0.7; margin-bottom: 6px; }

/* Typing dots */
.typing {
  display:inline-flex; gap:4px; align-items:center; margin-left:4px;
}
.dot { width:6px; height:6px; border-radius:50%; background:#8bd3ff; opacity:0.4; animation: blink 1.2s infinite; }
.dot:nth-child(2){ animation-delay: .2s; }
.dot:nth-child(3){ animation-delay: .4s; }
@keyframes blink { 0%,100%{opacity:0.2;} 50%{opacity:1;} }

/* Control panel */
.panel {
  padding: 14px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.06);
  background: linear-gradient(135deg, rgba(25,25,50,0.6), rgba(18,18,36,0.6));
  box-shadow: 0 8px 22px rgba(0,0,0,0.25);
}
.small { font-size: 12px; opacity: 0.85; }

/* Buttons */
.stButton > button {
  border-radius: 12px !important;
  border: 1px solid rgba(130,130,255,0.25) !important;
  background: linear-gradient(135deg, #10142a, #0e1630) !important;
  color: #d8e9ff !important;
  padding: 8px 14px !important;
}
.stTextInput > div > div > input, .stTextArea textarea {
  background: rgba(10,10,20,0.75) !important;
  color: #e9f2ff !important;
  border-radius: 10px !important;
  border: 1px solid rgba(140,140,255,0.18) !important;
}
</style>
"""
st.markdown(ROBO_CSS, unsafe_allow_html=True)

# =========================
# HEADER
# =========================
colA, colB = st.columns([1, 6])
with colA:
    st.markdown(
        """
        <div class="robo-face">
          <div class="robo-vis">
            <div class="robo-eye"></div>
            <div class="robo-eye"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with colB:
    st.markdown(
        """
        <div class="robo-header">
          <div style="display:flex; flex-direction:column;">
            <div class="robo-title">Robo Assistant — SAP S/4HANA Address Helper</div>
            <div class="robo-sub">Postal • Telephone • Fax — smart, confirm-first updates</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =========================
# SIDEBAR
# =========================
st.sidebar.title("⚙️ Settings")
api_url = st.sidebar.text_input("API URL", value=DEFAULT_API_URL, help="FastAPI /chat endpoint")
st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Quick Actions")
qa_col1, qa_col2 = st.sidebar.columns(2)
if qa_col1.button("Show address types"):
    st.session_state.setdefault("queue", []).append("Show available address types")
if qa_col2.button("Update postal"):
    st.session_state.setdefault("queue", []).append("Update postal address for plant 1000")

qa_col3, qa_col4 = st.sidebar.columns(2)
if qa_col3.button("Set phone"):
    st.session_state.setdefault("queue", []).append("Set telephone number for plant 1000 to +91-9876543210")
if qa_col4.button("Set fax"):
    st.session_state.setdefault("queue", []).append("Set fax number for plant 1000 to 020-555-1212")

st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Tips", expanded=False):
    st.markdown(
        "- Use natural language; the assistant will guide required keys first.\n"
        "- It always asks for confirmation before executing.\n"
        "- Expand ‘Control JSON’ to see the machine-readable state."
    )

# =========================
# SESSION STATE
# =========================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "control_state" not in st.session_state:
    st.session_state.control_state = {}
if "queue" not in st.session_state:
    st.session_state.queue = []

# =========================
# CHAT RENDER
# =========================
def render_bubble(role: str, content: str):
    klass = "assistant" if role == "assistant" else "user"
    who = "🤖 Robo" if role == "assistant" else "🧑 You"
    st.markdown(
        f"""
        <div class="chat-wrap">
          <div class="bubble {klass}">
            <div class="meta">{who}</div>
            <div>{content}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

for m in st.session_state.messages:
    render_bubble(m["role"], m["content"])

# =========================
# CONFIRMATION BAR
# =========================
def show_confirmation_bar(control_state: dict):
    if not isinstance(control_state, dict):
        return
    if control_state.get("action") != "confirm":
        return
    st.markdown("### 🔒 Confirmation Required")
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            st.markdown("**Planned Action**")
            svc = control_state.get("service", "")
            ent = control_state.get("entity", "")
            method = control_state.get("method", "")
            key = control_state.get("key_field", "")
            st.caption(f"- Service: `{svc}`\n- Entity: `{ent}`\n- Method: `{method}`\n- Key: `{key}`")
            payload = control_state.get("payload") or {}
            if payload:
                st.caption("**Payload**")
                st.json(payload, expanded=False)

        with right:
            st.markdown("**Confirm or Cancel**")
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirm", use_container_width=True):
                st.session_state.user_to_send = "confirm"
            if c2.button("❌ Cancel", use_container_width=True):
                st.session_state.user_to_send = "cancel"

show_confirmation_bar(st.session_state.control_state)

# =========================
# INPUT AREA
# =========================
def send_to_backend(text: str):
    try:
        payload = {"user": text, "state": st.session_state.control_state}
        res = requests.post(api_url, json=payload, timeout=90)
        res.raise_for_status()
        data = res.json()
        reply = data.get("reply", "⚠️ No reply received.")
        control = data.get("state", {})
        return reply, control
    except Exception as e:
        return f"❌ Backend error: {e}", {"action": "error", "message": str(e)}

# queued quick actions
if st.session_state.queue:
    qa_text = st.session_state.queue.pop(0)
    render_bubble("user", qa_text)
    with st.spinner("Robo is thinking"):
        # typing animation
        st.markdown('<span class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>', unsafe_allow_html=True)
        time.sleep(0.35)
        reply, control = send_to_backend(qa_text)
    render_bubble("assistant", reply)
    st.session_state.messages.append({"role": "user", "content": qa_text})
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.control_state = control

# free-form input
user_text = st.chat_input("Message Robo…")
if "user_to_send" in st.session_state:
    # confirm/cancel clicked
    user_text = st.session_state.pop("user_to_send")

if user_text:
    render_bubble("user", user_text)
    with st.spinner("Robo is thinking"):
        st.markdown('<span class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>', unsafe_allow_html=True)
        time.sleep(0.35)
        reply, control = send_to_backend(user_text)
    render_bubble("assistant", reply)
    st.session_state.messages.append({"role": "user", "content": user_text})
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.control_state = control

# =========================
# CONTROL JSON INSPECTOR
# =========================
st.markdown("### 🧩 Control JSON")
with st.expander("View conversation control state", expanded=False):
    st.json(st.session_state.control_state or {}, expanded=False)

# =========================
# FOOTER
# =========================
st.markdown(
    """
    <div class="small" style="opacity:0.6; margin-top: 8px;">
      <span>🤖 Robo Assistant • SAP S/4HANA Address Helper</span>
      &nbsp;•&nbsp;<span>Confirm-first execution • Smart field planning</span>
    </div>
    """,
    unsafe_allow_html=True,
)
