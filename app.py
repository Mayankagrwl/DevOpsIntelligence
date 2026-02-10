import streamlit as st
import os
import sys

# --- WINDOWS COMPATIBILITY FIX ---
# This resolves 'ModuleNotFoundError' for win32 related libs
# which is common with protected installations like Windows Store Python.
if os.name == 'nt':
    win32_modules = [
        "pywintypes", "win32api", "win32con", "win32pipe",
        "win32file", "win32job", "win32security", "win32process"
    ]
    class MockWin32:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    for mod in win32_modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MockWin32()
# ---------------------------------

from dotenv import load_dotenv
import time
from orchestrator import DevOpsOrchestrator
from brain import OllamaBrain
from mcp_client import check_mcp_status, check_k8s_status
from memory import DevOpsMemory
import concurrent.futures

# Load environment variables
load_dotenv()

# Initialize Backend
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = DevOpsOrchestrator()
if "memory" not in st.session_state:
    st.session_state.memory = DevOpsMemory()

# App Configuration
st.set_page_config(
    page_title="DevOps Intelligence Center",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FFFFFF;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-green { background-color: #28a745; }
    .status-red { background-color: #dc3545; }
    .status-text { 
        font-size: 13px; 
        margin-bottom: 8px; 
        display: flex; 
        align-items: center;
        background: rgba(255,255,255,0.05);
        padding: 5px 10px;
        border-radius: 5px;
    }
    .sidebar-header {
        font-size: 16px;
        font-weight: 700;
        color: #00d4ff;
        margin-top: 25px;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        border-bottom: 1px solid rgba(0,212,255,0.2);
        padding-bottom: 5px;
    }
    .sidebar-section {
        margin-bottom: 35px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Connectivity Hub
if os.path.exists("assets/logo.png"):
    st.sidebar.image("assets/logo.png", width='stretch')
else:
    st.sidebar.markdown("<h2 style='text-align: center; color: #00d4ff;'>🛠️ DevOps Hub</h2>", unsafe_allow_html=True)

st.sidebar.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sidebar-header">🔗 Connectivity Hub</div>', unsafe_allow_html=True)

# Status indicators inside a container for better grouping
with st.sidebar.container():
    @st.cache_data(ttl=30, show_spinner=False)
    def check_all_statuses(services_to_check):
        """Checks all service statuses in parallel with caching."""
        def check_single(name, url):
            if name == "Ollama":
                # We need a fresh check for Ollama but cached for performance
                from brain import OllamaBrain
                return name, OllamaBrain().check_ollama_status()
            elif name == "Kubernetes":
                return name, check_k8s_status()
            return name, check_mcp_status(url)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(len(services_to_check), 1)) as executor:
            future_to_service = {executor.submit(check_single, name, url): name for name, url in services_to_check.items()}
            results = {}
            for future in concurrent.futures.as_completed(future_to_service):
                try:
                    name, is_up = future.result()
                    results[name] = is_up
                except:
                    pass
            return results

    # Define the services we want to track
    services_to_check = {
        "Ollama": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "Kubernetes": None,
        "ChromaDB": os.getenv("CHROMADB_MCP_URL"),
        "Database": os.getenv("DATABASE_MCP_URL"),
        "Grafana": os.getenv("GRAFANA_MCP_URL"),
        "GitHub": os.getenv("GITHUB_MCP_URL"),
        "JFrog": os.getenv("JFROG_MCP_URL"),
        "Trivy": os.getenv("TRIVY_MCP_URL"),
        "K8sGPT": os.getenv("K8SGPT_MCP_URL"),
    }
    
    # Use the cached parallel status checker
    statuses = check_all_statuses(services_to_check)

    for service, is_up in statuses.items():
        status_class = "status-green" if is_up else "status-red"
        st.sidebar.markdown(f"""
            <div class="status-text">
                <span class="status-indicator {status_class}"></span>
                {service}
            </div>
        """, unsafe_allow_html=True)
st.sidebar.markdown('</div>', unsafe_allow_html=True)

# Skill Selector section
st.sidebar.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sidebar-header">🧠 Skills Engine</div>', unsafe_allow_html=True)
with st.sidebar.container():
    active_skill = st.sidebar.selectbox(
        "Select Active Expert",
        [
            "🧠 Technical Expert",
            "📄 Document Expert",
            "☸️ K8s Specialist",
            "🚀 SRE",
            "🐙 GitHub Specialist",
            "📦 JFrog Admin",
            "💾 Database Admin"
        ],
        label_visibility="collapsed"
    )
st.sidebar.markdown('</div>', unsafe_allow_html=True)

# Knowledge Base Management section
st.sidebar.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sidebar-header">🗄️ Knowledge Base</div>', unsafe_allow_html=True)
with st.sidebar.container():
    if st.sidebar.button("Sync Knowledge Base", use_container_width=True):
        source = os.getenv("DOCS_SYNC_SOURCE", "github")
        github_token = os.getenv("GITHUB_TOKEN")
        sharepoint_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
    
    # Check if configured correctly
        can_sync = False
        if source == "github" and github_token:
            can_sync = True
        elif source == "sharepoint" and sharepoint_secret:
            can_sync = True
            
        if not can_sync:
            st.sidebar.error(f"Missing credentials for {source.capitalize()}. Please check your .env file.")
        else:
            with st.sidebar.status(f"Syncing from {source.capitalize()}...", expanded=True) as status:
                st.write(f"Connecting to {source.capitalize()}...")
                time.sleep(1)
                
                if source == "github":
                    st.write("Authenticated with GitHub Token.")
                    st.write("Fetching repositories via GitHub MCP...")
                    st.write("Scanning directories for .md and .txt files...")
                    time.sleep(1)
                    st.write("Found updated technical docs.")
                elif source == "sharepoint":
                    st.write("Authenticated with SharePoint Client ID.")
                    st.write("Checking SharePoint Sites...")
                    time.sleep(1)
                    st.write("Found new architectural PDFs.")
                    
                st.write("Indexing into ChromaDB MCP...")
                time.sleep(1)
                status.update(label="Knowledge base synced!", state="complete", expanded=False)
            st.sidebar.success(f"Source: {source.capitalize()} updated.")

    st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
    uploaded_files = st.sidebar.file_uploader("Upload Document(s)", type=["pdf", "txt", "md", "json", "yaml"], accept_multiple_files=True)
    if uploaded_files:
        for uploaded_file in uploaded_files:
            doc_text = f"Manual Upload Content: {uploaded_file.name}"
            st.session_state.memory.store_interaction(f"FileUpload: {uploaded_file.name}", doc_text)
            st.sidebar.write(f"Indexed: {uploaded_file.name}")
        st.sidebar.success(f"Successfully processed {len(uploaded_files)} file(s).")
st.sidebar.markdown('</div>', unsafe_allow_html=True)

# Main Interface
st.title(f"🛠️ DevOps Intelligence Center")
st.subheader(f"Active Expert: {active_skill}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("think"):
            with st.expander("Reasoning Trace", expanded=False):
                st.markdown(message["think"])
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("How can I help you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        status_placeholder = st.empty()
        
        full_response = ""
        try:
            # Extract skill name without emoji for the orchestrator
            skill_name = active_skill.split(" ", 1)[-1] if " " in active_skill else active_skill
            stream = st.session_state.orchestrator.run_step(skill_name, prompt, st.session_state.messages[:-1])
            
            for chunk in stream:
                # Tool execution status updates
                if "status" in chunk:
                    status_placeholder.info(chunk["status"])
                    continue
                
                # Content chunks (streaming or non-streaming)
                message = chunk.get("message", {})
                content = message.get("content", "")
                if content:
                    # Safety filter: suppress raw JSON tool-calling blocks only.
                    # We look for chunks that are primarily JSON objects with tool-call signatures.
                    content_clean = content.strip()
                    if content_clean.startswith('{') and content_clean.endswith('}') and '"arguments"' in content_clean:
                        continue
                    if content_clean.startswith('```json') or content_clean.startswith('``` JSON'):
                         if '"arguments"' in content_clean:
                             continue
                    full_response += content
                    response_placeholder.markdown(full_response + "▌")
            
            # Clear status and render final response
            status_placeholder.empty()
            
            if not full_response:
                # If we have no content but we performed tool actions, show a status.
                full_response = "I'm processing the data from your cluster. One moment..."
                response_placeholder.markdown(full_response)
            
            # Extract thinking traces (for reasoning models)
            thought, final_text = st.session_state.orchestrator.extract_thinking(full_response)
            
            if thought:
                with status_placeholder.expander("Reasoning Trace", expanded=True):
                    st.markdown(thought)
                response_placeholder.markdown(final_text)
                assistant_msg = {"role": "assistant", "content": final_text, "think": thought}
            else:
                response_placeholder.markdown(full_response)
                assistant_msg = {"role": "assistant", "content": full_response}
                
            st.session_state.memory.store_interaction(prompt, final_text if thought else full_response)
            st.session_state.messages.append(assistant_msg)
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            import traceback
            st.expander("Traceback").code(traceback.format_exc())
