# 🌈 RainbowHole V0 — Decentralized Sovereign AI Node

**Status:** In Development · **Stack:** Python 3.14, FastAPI, Streamlit, Ollama · **License:** MIT

---

## Abstract

RainbowHole is a decentralized, P2P-supported framework designed to ensure **cognitive sovereignty**. In an era of "Intelligence-as-a-Service" monopolies, RainbowHole deconstructs the dependency on centralized cloud infrastructures.

The system integrates **local inference engines**, **content-addressed storage**, and **asynchronous consensus mechanisms** into a resilient knowledge mesh. The objective is the operation of an **autonomous intelligence cell** that runs primarily on local hardware and regenerative energy (off-grid).

> *The ghosts are in the machine.*

---

## System Philosophy & Problem Statement

Centralized Large Language Models (LLMs) are subject to three systemic risks:

| Risk | Description |
|------|-------------|
| **Information Asymmetry** | Proprietary gatekeepers control access to collective knowledge. |
| **Algorithmic Alignment** | External ethical constraints function as a filtering layer (*censorship-by-design*). |
| **Structural Fragility** | Dependence on monetary paywalls and physical cloud infrastructure. |

RainbowHole addresses these risks through the **primacy of local inference** and the **principle of the commons**.

---

## Architecture — The Triple Layer

The system is divided into three functional layers that interact **asynchronously**.

### Layer I — The Sovereign Node (Compute)

The compute unit executes inference locally.

**Current Implementation:**
- **LocalProvider** — inference via [Ollama](https://ollama.com) HTTP API (`phi3:mini`, Qwen, etc.)
- **RemoteProvider** — forwards inference to a VPS via HTTP/SSE with exponential backoff retry
- **BrainRouter** — strategy-pattern orchestrator supporting three modes:
  - `local` — Ollama only
  - `remote` — VPS only
  - `auto` — remote-first with automatic local fallback on failure
- **Memory guard** — `psutil` RAM check before local inference to prevent OOM

#### Model Strategy

Use of **Small Language Models (SLMs)** such as Qwen2.5-Coder and Phi-3, optimized for low memory latency.

#### Privacy Isolation

All raw prompts and intermediate activations remain in the **volatile memory (RAM/VRAM)** of the local node.

---

### Layer II — Distributed Knowledge Mesh (Memory)

Instead of burying knowledge inside model weights, RainbowHole utilizes an **external decentralized memory**.

**Current Implementation:**
- **ContentAddressableStorage** — proto-IPFS vault: files stored on disk keyed by **SHA-256 CID** (Content Identifier)
- **JSON index** (`_index.json`) — tracks CID, filename, size, MIME type, timestamp, sync status
- **Cross-node sync** — push/pull files between local and remote vaults, diff comparison
- **Deduplication** — same content → same CID, stored once

---

### Layer III — Collective Intelligence Protocol (Network)

Networking of nodes to form a swarm.

**Current Implementation:**
- **HeartbeatMonitor** — async background task pinging peer node for latency + GPU status
- **SSE streaming** — server-sent events for real-time token-by-token inference
- **GPU query** — `nvidia-smi` integration for utilization, VRAM, temperature
- **Sliding window** latency tracking (10-sample deque for jitter analysis)

---

## Quick Start

### Prerequisites

- Python 3.14+
- [Ollama](https://ollama.com) installed and running
- At least one model pulled (e.g., `ollama pull phi3:mini`)

### Installation

```bash
git clone https://github.com/DIFFERENTPROGRESS/RainbowHole-AI-Ecosystem.git
cd RainbowHole-AI-Ecosystem

pip install -r requirements.txt
```

### Configuration

Edit `.env` to match your environment:

```
NODE_TYPE=local
BRAIN_MODE=local
LOCAL_MODEL=phi3:mini
API_PORT=8000
```

### Running

```bash
# Terminal 1: API server
python -m api.routes
# → FastAPI running on http://localhost:8000

# Terminal 2: Streamlit UI
streamlit run ui/interface.py
# → Dashboard at http://localhost:8501
```

### VPS Deployment

```bash
sudo bash setup_vps.sh
```

The script auto-detects Docker vs standard VPS and configures:
- System dependencies (curl, git, python3-venv, zstd)
- Ollama installation
- Python virtual environment + FastAPI/Uvicorn
- systemd service (`rainbowhole`) for autostart
- API key generation

---

## API Reference

All endpoints defined in `api/routes.py`. Sensitive endpoints require `Authorization: Bearer <API_KEY>` header.

### Health & Info

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Node status, brain mode, Ollama/ VPS connectivity |
| `GET` | `/api/node/info` | Static config (node type, model, vault path, port) |

### Inference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/inference` | Non-streaming generation. Body: `InferenceRequest` JSON. |
| `POST` | `/api/inference/stream` | SSE streaming. Yields `event: token` → `event: done`. |

### Vault (Storage)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/vault/upload` | Upload file → stored by SHA-256 CID |
| `GET` | `/api/vault/index` | List all files with metadata |
| `GET` | `/api/vault/{cid}` | Download file by CID |
| `POST` | `/api/vault/sync` | Receive synced file from peer |
| `GET` | `/api/vault/diff` | Compare local vs remote index |

### Models

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/models` | List available Ollama models |
| `POST` | `/api/models/select` | Switch active model (`name` form field) |

### Monitoring

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/pulse` | Heartbeat: latency, GPU stats, uptime, vault file count |
| `GET` | `/api/logs` | Recent log entries (ring buffer, last 300) |

---

## Configuration

### Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_TYPE` | `local` | Node identity: `local` or `remote` |
| `BRAIN_MODE` | `auto` | Inference routing: `local`, `remote`, or `auto` |
| `VPS_URL` | *(empty)* | Remote VPS endpoint URL |
| `API_KEY` | *(auto)* | Shared secret for inter-node auth |
| `LOCAL_MODEL` | `phi3:mini` | Default Ollama model |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama HTTP endpoint |
| `VAULT_PATH` | `./vault` | Content-addressed storage directory |
| `HEARTBEAT_INTERVAL` | `10` | Peer ping interval in seconds |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API listen port |
| `API_BASE` | `http://localhost:8000` | Base URL for Streamlit UI |

### Shared Models (`shared/schemas.py`)

All inter-node communication uses Pydantic v2 models:

| Model | Purpose |
|-------|---------|
| `InferenceRequest` | Prompt, model, temperature, max_tokens, brain_mode, system_prompt, `context_cids` (planned) |
| `InferenceResponse` | Generated text, model, tokens_used, latency_ms, provider |
| `InferenceChunk` | Streamed token, finish_reason, model, latency_ms |
| `BrainMode` | Enum: `local`, `remote`, `auto` |
| `NodeType` | Enum: `local`, `remote` |
| `SyncStatus` | Enum: `local_only`, `remote_only`, `synced`, `unknown` |
| `FileMetadata` | CID, filename, size_bytes, timestamp, mime_type, sync_status |
| `SyncResponse` | CID, status (`accepted`/`already_exists`/`error`), message |
| `VaultDiffResponse` | local_only, remote_only, synced file lists |
| `HeartbeatResponse` | node_id, status, latency_ms, gpu_info, uptime, vault_file_count |
| `GPUInfo` | GPU name, utilization %, VRAM used/total, temperature |
| `NodeInfo` | Static node configuration object |
| `ErrorResponse` | Standard error envelope |

---

## Project Structure

```
RainbowHole-AI-Ecosystem/
├── api/                    # FastAPI application
│   ├── __init__.py
│   └── routes.py           # 12 endpoints (health, inference, vault, models, pulse, logs)
├── core/                   # Core engine
│   ├── __init__.py
│   ├── brain.py            # BrainRouter, LocalProvider, RemoteProvider
│   ├── vault.py            # ContentAddressableStorage (SHA-256 CID)
│   ├── pulse.py            # HeartbeatMonitor (peer health + GPU)
│   └── logs.py             # LogBuffer (ring-buffer for terminal UI)
├── shared/                 # Shared contracts
│   ├── __init__.py
│   └── schemas.py          # All Pydantic v2 models
├── ui/                     # Streamlit dashboard
│   ├── __init__.py
│   └── interface.py        # Neural Bridge (chat) + Data Shards (vault)
├── vault/                  # Content-addressed file storage
│   ├── _index.json         # CID → metadata index
│   ├── <sha256-hash>       # Stored blobs
│   └── <sha256-hash>
├── .env                    # Local configuration
├── .gitignore
├── requirements.txt        # Python dependencies
├── setup_vps.sh            # VPS deployment script (systemd/Docker)
├── payload.tar.gz          # VPS deployment tarball
└── README.md               # This file
```

---

## The Incentive Model — Unit of Reason (UoR)

*Planned — not yet implemented in V0.*

To address the **free-rider problem** in P2P networks, RainbowHole implements a contribution-based prioritization mechanism.

### UoR Credits

Nodes earn credits by:
- Providing persistent storage for IPFS chunks
- Validating inference results of other nodes
- Exporting inference cycles during periods of solar energy surplus

### Service Level Agreements (SLA)

Higher UoR balances allow access to larger model instances within the swarm (e.g., GPU sharing via the Petals protocol).

---

## Hardware Requirements

| Component | Minimal (Guerilla) | Recommended (Sovereign) |
|-----------|-------------------|------------------------|
| CPU / RAM | 8 GB RAM (DDR4/5) | 64 GB Unified Memory (Apple M-Series) |
| GPU | Shared Memory / iGPU | RTX 3090 / 4090 (24 GB VRAM) |
| Storage | 512 GB NVMe SSD | 4 TB+ RAID (IPFS persistence) |
| Network | Broadband | Broadband + Static IP |
| Energy | Grid power | Solar-supported LiFePO₄ battery bank |

---

## Security & Integrity

- **API key authentication** — Bearer token required on all sensitive endpoints (`_verify_key()` middleware)
- **Memory guard** — RAM threshold check prevents OOM crashes

---

## Dependencies

```
fastapi            # REST + SSE API framework
uvicorn            # ASGI server
sse-starlette      # Server-Sent Events
httpx              # Async HTTP client (Ollama + VPS)
pydantic           # Data validation (all models)
pydantic-settings
aiofiles           # Async file I/O for vault
python-dotenv      # Environment configuration
streamlit          # Web dashboard UI
psutil             # Memory/CPU monitoring
```

---

## Roadmap & Further Steps

All planned work beyond V0, organized by theme.

### V0 — Scaffolding (Current ✅)

- Python orchestration framework
- FastAPI REST + SSE API (12 endpoints)
- Streamlit dark-themed UI (chat + vault tabs)
- Local inference via Ollama (`LocalProvider`)
- Remote inference via VPS (`RemoteProvider` with retry)
- BrainRouter auto-fallback mode
- Content-addressed vault (SHA-256 CID on local filesystem)
- Cross-node vault sync (push/pull/diff)
- Heartbeat pulse monitor with GPU stats
- Memory-guarded inference (psutil RAM check)
- API key authentication
- VPS deployment script (systemd + Docker)

### Phase 2 — Autonomy Mode (Next 🔜)

- **Vectorized RAG** — automatic chunk + embed on vault store using ChromaDB or Orama
- **Context injection** — pull relevant vault CIDs as context into inference prompts
- **Semantic search** — cosine similarity over embedding space for document retrieval
- **8 GB RAM optimization** — fit entire pipeline within low-memory constraint
- **3B parameter SLMs** — model strategy using Qwen2.5-Coder, Phi-3, etc.
- **Remove external API dependencies** — fully local operation
- **Model weight integrity** — SHA-256 verification against a decentralized registry

### Phase 3 — Mesh Network (Planned 🔮)

- **IPFS daemon** — integrate go-ipfs/kubo for true content-addressed distributed storage
- **DHT-based CID routing** — locate content across swarm nodes without central index
- **libp2p + WebRTC** — P2P mesh networking to bypass NAT barriers
- **Consensus of Reason (CoR)** — probabilistic validation algorithm

  ```
  R_final = centroid({O₁, O₂, ..., Oₙ})
  accept if σ(O₁..ₙ) < τ
  ```

- **Swarm mode for BrainRouter** — route inference across peer nodes
- **Deltas & Snapshots** — knowledge updates as incremental layers

### Phase 4 — Distributed Inference (Planned 🔮)

- **Petals protocol** — run large models collaboratively across swarm GPUs
- **PetalsProvider** — new inference backend replacing RemoteProvider for P2P mode
- **GPU sharing** — contribute idle VRAM to the swarm, earn UoR credits
- **Distributed model serving** — split transformer layers across peers

### Phase 5 — Incentives & Economics (Planned 🔮)

- **Unit of Reason (UoR)** — contribution-based credit system
- **UoR mining** — earn credits by:
  - Providing persistent storage for IPFS chunks
  - Validating inference results of other nodes
  - Exporting inference cycles during solar energy surplus
- **SLA tiers** — higher UoR balance unlocks larger model instances
- **Sybil protection** — Proof-of-Useful-Work for reputation weighting

### Phase 6 — Hardening & Autonomy (Planned 🔮)

- **End-to-end encryption** for all P2P communication
- **Off-grid operation** — solar-supported LiFePO₄ battery bank
- **Autonomous mode** — self-healing node with automatic peer discovery
- **Regenerative energy scheduling** — defer intensive inference to solar peaks

---

## Status

**In Development — V0**

RainbowHole represents a departure from the **monolithic AI paradigm**. It replaces **vertical scaling** (larger models in centralized data centers) with **horizontal cooperation** (many specialized local models). The mathematical robustness of the system emerges from the **decoupling of language processing (LLM)** and **factual information (IPFS-RAG)**.

> The ghosts are in the machine.
