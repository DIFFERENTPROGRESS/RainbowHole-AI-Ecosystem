"""
RainbowHole V0 — The Interface
Dark-themed Streamlit UI with Neural Bridge (chat) and Data Shards (vault) tabs.
"""
from __future__ import annotations
import json, os, time
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════

API_BASE = os.getenv("API_BASE", f"http://localhost:{os.getenv('API_PORT', '8000')}")
API_KEY = os.getenv("API_KEY", "")
AUTH_HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

st.set_page_config(
    page_title="RainbowHole V0 — Sovereign AI Node",
    page_icon="🌈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════
# Custom CSS — Dark Neon Theme
# ═══════════════════════════════════════════════════

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg-primary: #0a0a0f;
        --bg-secondary: #12121a;
        --bg-card: #1a1a2e;
        --bg-card-hover: #1e1e35;
        --accent-cyan: #00f5ff;
        --accent-purple: #bf5af2;
        --accent-green: #30d158;
        --accent-red: #ff453a;
        --accent-orange: #ff9f0a;
        --text-primary: #e5e5ea;
        --text-secondary: #8e8e93;
        --border-dim: #2c2c3a;
        --glow-cyan: 0 0 20px rgba(0, 245, 255, 0.15);
        --glow-purple: 0 0 20px rgba(191, 90, 242, 0.15);
    }

    .stApp {
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0d0d1a 50%, #0a0f14 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        min-width: 280px !important;
        max-width: 280px !important;
        background: linear-gradient(180deg, #0d0d1a 0%, #12121f 100%);
        border-right: 1px solid var(--border-dim);
    }

    /* Chat messages */
    .stChatMessage {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-dim) !important;
        border-radius: 12px !important;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border-dim);
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] {
        color: var(--accent-cyan) !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: var(--bg-card);
        border: 1px solid var(--border-dim);
        border-radius: 8px 8px 0 0;
        color: var(--text-secondary);
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0,245,255,0.1), rgba(191,90,242,0.1));
        border-color: var(--accent-cyan) !important;
        color: var(--accent-cyan) !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, rgba(0,245,255,0.15), rgba(191,90,242,0.15));
        border: 1px solid var(--accent-cyan);
        color: var(--accent-cyan);
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(0,245,255,0.3), rgba(191,90,242,0.3));
        box-shadow: var(--glow-cyan);
    }

    /* Status indicators */
    .status-online { color: var(--accent-green); }
    .status-offline { color: var(--accent-red); }
    .status-degraded { color: var(--accent-orange); }

    /* File table */
    .vault-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85em;
    }
    .vault-table th {
        background: var(--bg-card);
        color: var(--accent-cyan);
        padding: 10px 12px;
        text-align: left;
        border-bottom: 2px solid var(--accent-cyan);
    }
    .vault-table td {
        padding: 8px 12px;
        border-bottom: 1px solid var(--border-dim);
        color: var(--text-primary);
    }
    .vault-table tr:hover td {
        background: var(--bg-card-hover);
    }
    .cid-cell {
        color: var(--accent-purple);
        cursor: pointer;
    }
    .synced-badge {
        background: rgba(48,209,88,0.15);
        color: var(--accent-green);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
    }
    .local-badge {
        background: rgba(255,159,10,0.15);
        color: var(--accent-orange);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
    }

    /* Pinned terminal bar */
    .main > .block-container {
        padding-bottom: 940px !important;
    }
    #rh-terminal {
        position: fixed;
        bottom: 0;
        left: 280px;
        right: 0;
        z-index: 9999;
        background: #0a0a0f;
        border-top: 1px solid var(--border-dim);
        padding: 6px 16px 10px 16px;
        font-family: 'JetBrains Mono', monospace;
    }
    #rh-terminal .term-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #8e8e93;
        font-size: 0.85em;
        margin-bottom: 4px;
    }
    #rh-terminal .term-header button {
        background: none;
        border: 1px solid #2c2c3a;
        color: #8e8e93;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.9em;
        padding: 2px 10px;
    }
    #rh-terminal .term-header button:hover {
        color: var(--accent-cyan);
        border-color: var(--accent-cyan);
    }
    #rh-terminal .term-body {
        max-height: 900px;
        overflow-y: auto;
        font-size: 0.85em;
        line-height: 1.5;
        color: #e5e5ea;
        white-space: pre-wrap;
    }
    #rh-terminal .term-body::-webkit-scrollbar {
        width: 4px;
    }
    #rh-terminal .term-body::-webkit-scrollbar-track {
        background: #12121a;
    }
    #rh-terminal .term-body::-webkit-scrollbar-thumb {
        background: #2c2c3a;
        border-radius: 2px;
    }

    /* Header */
    .rh-header {
        text-align: center;
        padding: 10px 0 20px 0;
    }
    .rh-header h1 {
        background: linear-gradient(135deg, #00f5ff, #bf5af2, #ff453a);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2em;
        font-weight: 700;
        margin: 0;
    }
    .rh-header p {
        color: var(--text-secondary);
        font-size: 0.9em;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def api_get(path: str, timeout: float = 10.0):
    try:
        r = httpx.get(f"{API_BASE}{path}", headers=AUTH_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def api_post(path: str, **kwargs):
    try:
        r = httpx.post(f"{API_BASE}{path}", headers=AUTH_HEADERS, timeout=60.0, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def format_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ═══════════════════════════════════════════════════
# Sidebar — Pulse Monitor
# ═══════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div class="rh-header">
        <h1>🌈 RainbowHole</h1>
        <p>Sovereign AI Node V0</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Node health
    health = api_get("/health")
    if health:
        node_type = health.get("node", "unknown").upper()
        st.markdown(f"**Node Type:** `{node_type}`")
        st.markdown(f'<span class="status-online">● Online</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-offline">● API Offline</span>', unsafe_allow_html=True)
        st.warning("Cannot reach local API. Start it with:\n```\npython -m api.routes\n```")

    st.divider()

    # Pulse data
    pulse_data = api_get("/api/pulse")
    if pulse_data:
        col1, col2 = st.columns(2)
        latency = pulse_data.get("latency_ms")
        with col1:
            st.metric("Latency", f"{latency:.0f}ms" if latency else "N/A")
        with col2:
            st.metric("Uptime", f"{pulse_data.get('uptime_seconds', 0):.0f}s")

        gpu = pulse_data.get("gpu_info")
        if gpu and gpu.get("available"):
            st.markdown("**🎮 GPU Status**")
            st.text(f"  {gpu['name']}")
            st.progress(gpu["utilization_pct"] / 100, text=f"Util: {gpu['utilization_pct']:.0f}%")
            vram_pct = gpu["memory_used_mb"] / max(gpu["memory_total_mb"], 1)
            st.progress(vram_pct, text=f"VRAM: {gpu['memory_used_mb']:.0f}/{gpu['memory_total_mb']:.0f} MB")
            if gpu.get("temperature_c"):
                st.text(f"  Temp: {gpu['temperature_c']:.0f}°C")
        else:
            st.markdown("**🎮 GPU:** N/A")

        # VPS peer status
        st.divider()
        peer_st = pulse_data.get("status", "unknown")
        status_class = {"online": "status-online", "offline": "status-offline"}.get(peer_st, "status-degraded")
        st.markdown(f'**VPS Peer:** <span class="{status_class}">● {peer_st.upper()}</span>',
                    unsafe_allow_html=True)
        st.metric("Vault Files", pulse_data.get("vault_file_count", 0))

    st.divider()
    brain_mode = st.selectbox("🧠 Brain Mode", ["auto", "local", "remote"],
                               index=["auto", "local", "remote"].index(
                                   os.getenv("BRAIN_MODE", "auto")))
    st.caption(f"Mode: **{brain_mode}** | API: `{API_BASE}`")

    st.divider()

    # Available models
    models_data = api_get("/api/models")
    if models_data and models_data.get("models"):
        current_model = models_data["current"]
        st.markdown("**🤖 Ollama Models**")
        for m in models_data["models"]:
            if m == current_model:
                st.markdown(f'<span style="color:#00f5ff;font-weight:700;">▸ {m}</span>', unsafe_allow_html=True)
            else:
                if st.button(m, key=f"model_{m}", type="secondary", use_container_width=True):
                    api_post("/api/models/select", data={"name": m})
                    st.rerun()
    elif models_data is not None:
        st.markdown("**🤖 Ollama Models:** None")
    else:
        st.markdown("**🤖 Ollama:** Offline")


# ═══════════════════════════════════════════════════
# Main Tabs
# ═══════════════════════════════════════════════════

tab_chat, tab_vault = st.tabs(["⚡ Neural Bridge", "💎 Data Shards"])


# ── Tab 1: Neural Bridge (Chat) ──────────────────

with tab_chat:
    st.markdown("### ⚡ Neural Bridge — Streaming Inference")

    # Session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Enter your prompt…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""

            try:
                with httpx.stream(
                    "POST", f"{API_BASE}/api/inference/stream",
                    json={
                        "prompt": prompt, 
                        "stream": True, 
                        "temperature": 0.7, 
                        "max_tokens": 1024,
                        "brain_mode": brain_mode
                    },
                    headers=AUTH_HEADERS, timeout=120.0,
                ) as response:
                    response.raise_for_status()
                    current_event = "token"
                    try:
                        for line in response.iter_lines():
                            line = line.strip()
                            if not line:
                                continue
                            # SSE events are multi-line: "event: type\ndata: payload"
                            if line.startswith("event:"):
                                current_event = line[len("event:"):].strip()
                                continue
                            if line.startswith("data:"):
                                data_str = line[len("data:"):].strip()
                                if data_str == "[DONE]":
                                    break
                                # Handle error events from the server
                                if current_event == "error":
                                    try:
                                        err = json.loads(data_str)
                                        full_response = f"⚠️ **Server Error:** {err.get('error', data_str)}"
                                    except json.JSONDecodeError:
                                        full_response = f"⚠️ **Server Error:** {data_str}"
                                    break
                                # Normal token event
                                try:
                                    chunk = json.loads(data_str)
                                    token = chunk.get("token", "")
                                    if token:
                                        full_response += token
                                        placeholder.markdown(full_response + "▌")
                                except json.JSONDecodeError:
                                    continue
                    except httpx.RemoteProtocolError:
                        # SSE-starlette closes the connection after [DONE] without
                        # a proper chunked termination. If we already have content,
                        # this is a normal completion — not an error.
                        if not full_response:
                            full_response = "⚠️ **Stream interrupted** — The server closed the connection before sending any data."
            except httpx.ConnectError:
                full_response = "⚠️ **Connection Refused** — Cannot reach the API server. Ensure it's running with `python -m api.routes`."
            except httpx.RemoteProtocolError:
                # Can also occur outside the stream context on connection close
                if not full_response:
                    full_response = "⚠️ **Stream interrupted** — Connection lost before receiving data."
            except Exception as e:
                if not full_response:
                    full_response = f"⚠️ **Error:** {e}"

            placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Controls row
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        st.caption(f"{len(st.session_state.messages)} messages")


# ── Tab 2: Data Shards (Vault) ───────────────────

with tab_vault:
    st.markdown("### 💎 Data Shards — Content-Addressable Vault")

    # File upload
    uploaded = st.file_uploader("Drop files into the Vault", accept_multiple_files=True,
                                 type=None, key="vault_upload")
    if uploaded:
        for f in uploaded:
            data = f.read()
            result = api_post("/api/vault/upload", files={"file": (f.name, data, f.type or "application/octet-stream")})
            if "error" not in result:
                st.success(f"✅ `{f.name}` → CID: `{result.get('cid', '?')[:16]}…`")
            else:
                st.error(f"❌ Upload failed: {result.get('error')}")

    st.divider()

    # Vault index
    index = api_get("/api/vault/index")
    if index and len(index) > 0:
        # Build HTML table
        rows = ""
        for item in index:
            cid = item["cid"]
            sync = item.get("sync_status", "unknown")
            badge_class = "synced-badge" if sync == "synced" else "local-badge"
            rows += f"""<tr>
                <td class="cid-cell">{cid[:16]}…</td>
                <td>{item['filename']}</td>
                <td>{format_bytes(item['size_bytes'])}</td>
                <td><span class="{badge_class}">{sync}</span></td>
            </tr>"""

        st.markdown(f"""
        <table class="vault-table">
            <thead><tr><th>CID</th><th>Filename</th><th>Size</th><th>Sync</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
        """, unsafe_allow_html=True)

        # Sync controls
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Refresh Index"):
                st.rerun()
        with col2:
            if st.button("📤 Push All to VPS"):
                for item in index:
                    if item.get("sync_status") != "synced":
                        r = api_post("/api/vault/sync", data={"cid": item["cid"]})
                        st.write(f"  {item['cid'][:12]}… → {r.get('status', 'error')}")
        with col3:
            if st.button("📊 Show Diff"):
                diff = api_get("/api/vault/diff")
                if diff:
                    lo = diff.get("local_only", [])
                    ro = diff.get("remote_only", [])
                    sy = diff.get("synced", [])
                    st.info(f"**Synced:** {len(sy)} | **Local only:** {len(lo)} | **Remote only:** {len(ro)}")
    elif index is not None:
        st.info("Vault is empty. Upload files above to begin.")
    else:
        st.warning("Cannot reach API. Vault index unavailable.")


# ═══════════════════════════════════════════════════
# Cyberpunk Terminal (pinned bottom bar)
# ═══════════════════════════════════════════════════

log_data = api_get("/api/logs")

level_colors = {
    "DEBUG": "#8e8e93",
    "INFO": "#30d158",
    "WARNING": "#ff9f0a",
    "ERROR": "#ff453a",
    "CRITICAL": "#ff453a",
}
log_lines = []
if log_data and log_data.get("logs"):
    for entry in log_data["logs"][-100:]:
        c = level_colors.get(entry["level"], "#8e8e93")
        log_lines.append(f'<span style="color:{c};">[{entry["time"]}] [{entry["level"]}] {entry["message"]}</span>')

log_html = "\n".join(log_lines) if log_lines else '<span style="color:#8e8e93;">── idle ──</span>'

terminal_html = """<div id="rh-terminal">
  <div class="term-header">
    <span>┌─[ RAINBOWHOLE TERMINAL ]────────────────────────────┐</span>
    <span id="rh-term-refresh" style="cursor:pointer;">↻</span>
  </div>
  <div class="term-body">__LOG_CONTENT__</div>
</div>
<script>
(function() {
  var btn = document.getElementById('rh-term-refresh');
  if (btn) { btn.onclick = function() { location.reload(); }; }
  setTimeout(function() { location.reload(); }, 8000);
})();
</script>"""
st.markdown(terminal_html.replace("__LOG_CONTENT__", log_html), unsafe_allow_html=True)
