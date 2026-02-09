PRD: DevOps AI Intelligence Center (v1.4)

1. Project OverviewGoal: A centralized, professional AI command center for 5 engineers to manage Kubernetes and database resources using local LLMs.

Core Stack: Streamlit (UI), Ollama (Brain), Model Context Protocol (MCP) (Hands), and ChromaDB (Memory).

2. System Architecture & Integration

A. The "Brain" (Ollama) Model: qwen2.5-coder:7b-instruct-q4_k_m 
Hosting: Local instance on Port 11434.
Resource Goal: Optimized for 10 CPU / 16GB RAM environment.

B. The "Hands" (MCP Servers)
Kubernetes MCP: Connecting via SSE/HTTP to K8S_MCP_URL.
GitHub MCP(FUture): Source code and PR management.
JFrog MCP(Future): Artifact and binary management.
Trivy/Security MCP(Future): Security auditing (Port 8081).
Database MCP: (Future) Connection to MySQL/Postgres.
Grafana MCP: (Future) Connection to Grafana.
ChromaDB MCP: Connection to ChromaDB.

C.The "Memory" (ChromaDB)
  Persistence: Local directory /app/chroma_data.
  Embeddings: all-MiniLM-L6-v2 (Local/Low-CPU).
  Collection: devops_history.
  
3. Detailed Feature Requirements

I. Dashboard UI & UX
Visuals: High-contrast Dark Mode (layout="wide").
Sidebar Connectivity Hub: Real-time Status Lights (Green/Red) for:
  Ollama Status
  Kubernetes MCP Status
  ChromaDB 
  Grafana MCP Status
  Database MCP status
  GitHub MCP Status
  JFrog MCP Status
  Trivy MCP Status
  
StatusSkill Selector: st.sidebar.selectbox labeled "Active Agent Skill".

II. Dynamic Skills Engine & Model AllocationSystem prompts and specific models are assigned per skill via .env.

SkillPrimary ModelLogic / Focus

K8s Specialist  qwen2.5-coder:7b Tool-first, YAML generation, 16GB RAM optimization.
SRE / Obs llama3.1:8b   Root cause analysis via logs and metrics.
GitHub Specialist  qwen2.5-coder:7bPR management, workflow debugging, code review.
JFrog Admin  qwen2.5-coder:7b AQL searches, artifact auditing, Xray security.
Database Admin gemma3:4b SQL optimization, auditing, and schema management.
Technical Expert deepseek-r1:8 bMaster Orchestrator: Uses Chain-of-Thought to cross-reference GitHub, JFrog, and K8s.

III. Semantic Memory & RAG

Memory Logging: Every final resolution is embedded and stored in ChromaDB.

Hybrid RAG:
  Semantic Retrieval: Similarity search (distance < 0.5) before every query.
  Context Injection: "Relevant past context: [Retrieved Memory]" added to prompt.
  Future-Proofing: Placeholder logic included for "Documentation RAG" (PDF/Wiki ingestion).
  
  IV. Interaction & ReAct Loop
  
  User Input: Engineer types a request.
  Reasoning: LLM receives [System Prompt + User Query + Tool Definitions + RAG Context].
  Action: If LLM output includes a Tool Call, Python executes the MCP command.
  Observation: Tool output is shown in chat; LLM synthesizes a final response.
  
4. Technical Configuration (.env)

Code snippet# 
--- SYSTEM CONFIG ---
OLLAMA_URL="http://localhost:11434"
CHROMA_PATH="./chroma_data"

# --- MCP SERVER URLS ---
K8S_MCP_URL="http://mcp-k8s:8080/sse"
GITHUB_MCP_URL="http://mcp-github:8080/sse"
JFROG_MCP_URL="http://mcp-jfrog:8080/sse"
TRIVY_MCP_URL="http://mcp-trivy:8081/sse"

# --- MODEL ASSIGNMENTS ---
MODEL_TECH_EXPERT="deepseek-r1:8b-q4_K_M"
MODEL_K8S="qwen2.5-coder:7b-instruct-q4_K_M"
MODEL_SRE="llama3.1:8b-instruct-q4_K_M"
MODEL_GITHUB="qwen2.5-coder:7b-instruct-q4_K_M"
MODEL_JFROG="qwen2.5-coder:7b-instruct-q4_K_M"
MODEL_DB="gemma3:4b-q4_K_M"

# --- SKILL PROMPTS ---
PROMPT_K8S_SPECIALIST="### ROLE: Senior K8s Architect. Use kubectl tools to manage the cluster. Focus on resource limits for 16GB RAM constraints."
PROMPT_SRE_OBSERVABILITY="### ROLE: SRE. Focus on Grafana metrics and logs. Identify root causes of service degradation."
PROMPT_GITHUB_SPECIALIST="### ROLE: GitHub Automator. Manage PRs, Issues, and Actions. Debug failing CI/CD workflows."
PROMPT_JFROG_ADMIN="### ROLE: JFrog Expert. Search artifacts using AQL. Use Xray to audit image security before K8s deployment."
PROMPT_DB_ADMIN="### ROLE: Database Expert. Use MCP tools to audit MySQL and optimize slow queries."
PROMPT_TECH_EXPERT="### ROLE: Lead Architect. Orchestrate GitHub -> JFrog -> K8s. Use Chain-of-Thought reasoning to verify the entire supply chain."

# --- CREDENTIALS ---
GITHUB_TOKEN="ghp_xxx"
JFROG_TOKEN="jfrog_xxx"
JFROG_URL="https://org.jfrog.io"
DOCS_RAG_PATH="./docs_storage"

5. Implementation Roadmap

Step 1: Deploy K8s, GitHub, JFrog, and Trivy MCP servers in the cluster.
Step 2: Initialize persistent ChromaDB volume at /app/chroma_data.
Step 4: Deploy Streamlit app.py with the ReAct Loop and Model Switching logic.
Step 5: Finalize "Technical Expert" multi-tool orchestration using deepseek-r1.


When you select the Technical Expert, your Streamlit app should use deepseek-r1:8b. This model will "think" (showing the <think> block in your UI) to decide:
1.	"I need to check the GitHub PR first."
2.	"Now I will verify the artifact in JFrog."
3.	"Finally, I will check the Pod status in K8s."
