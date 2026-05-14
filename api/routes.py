"""
RainbowHole V0 — API Routes
FastAPI endpoints with SSE streaming, Vault CRUD, and Pulse health.
"""
from __future__ import annotations
import json, logging, os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from core.brain import BrainRouter
from core.logs import get_log_buffer
from core.pulse import HeartbeatMonitor
from core.vault import ContentAddressableStorage
from shared.schemas import (
    ErrorResponse, HeartbeatResponse, InferenceRequest, InferenceResponse,
    NodeInfo, NodeType, BrainMode, SyncResponse, VaultDiffResponse,
)

load_dotenv()
logger = logging.getLogger("rainbowhole.api")

# ── Globals (initialized in lifespan) ─────────────
brain: BrainRouter
vault: ContentAddressableStorage
pulse: HeartbeatMonitor


def _verify_key(authorization: str | None) -> None:
    """Simple shared-secret auth check."""
    expected = os.getenv("API_KEY", "")
    if not expected:
        return  # no key configured = open
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header.")
    token = authorization[len("Bearer "):]
    if token != expected:
        raise HTTPException(403, "Invalid API key.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global brain, vault, pulse
    get_log_buffer()  # initialise log capture
    brain = BrainRouter()
    vault = ContentAddressableStorage()
    pulse = HeartbeatMonitor()
    pulse.start()
    logger.info("RainbowHole node online.")
    yield
    pulse.stop()
    await brain.close()
    logger.info("RainbowHole node shut down.")


app = FastAPI(
    title="RainbowHole V0",
    description="P2P AI Framework — Decentralized Sovereign Network Node",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=True)


# ═══════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════

@app.get("/health")
async def health():
    brain_status = await brain.health()
    return {
        "status": "online", 
        "node": os.getenv("NODE_TYPE", "local"),
        "brain_mode": os.getenv("BRAIN_MODE", "auto"),
        "ollama_connected": brain_status.get("local", False),
        "vps_connected": brain_status.get("remote", False)
    }


@app.get("/api/node/info", response_model=NodeInfo)
async def node_info():
    return NodeInfo(
        node_type=NodeType(os.getenv("NODE_TYPE", "local")),
        brain_mode=BrainMode(os.getenv("BRAIN_MODE", "auto")),
        vault_path=os.getenv("VAULT_PATH", "./vault"),
        local_model=os.getenv("LOCAL_MODEL", "phi3:mini"),
        vps_url=os.getenv("VPS_URL", ""),
        api_port=int(os.getenv("API_PORT", "8000")),
    )


# ═══════════════════════════════════════════════════
# Inference
# ═══════════════════════════════════════════════════

@app.post("/api/inference", response_model=InferenceResponse)
async def inference(request: InferenceRequest,
                    authorization: str | None = Header(None)):
    _verify_key(authorization)
    try:
        return await brain.generate(request)
    except (ConnectionError, MemoryError) as exc:
        raise HTTPException(503, detail=str(exc))


@app.post("/api/inference/stream")
async def inference_stream(request: InferenceRequest,
                           authorization: str | None = Header(None)):
    _verify_key(authorization)

    async def event_gen() -> AsyncGenerator[dict, None]:
        try:
            async for chunk in brain.stream(request):
                yield {"event": "token", "data": chunk.model_dump_json()}
            yield {"event": "done", "data": "[DONE]"}
        except Exception as exc:
            logger.error(f"Stream error: {exc}", exc_info=True)
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(event_gen())


# ═══════════════════════════════════════════════════
# Vault — static routes FIRST to avoid {cid} collision
# ═══════════════════════════════════════════════════

@app.post("/api/vault/upload")
async def vault_upload(file: UploadFile = File(...),
                       authorization: str | None = Header(None)):
    _verify_key(authorization)
    data = await file.read()
    meta = await vault.store(data, file.filename or "unnamed", file.content_type)
    return meta.model_dump()


@app.get("/api/vault/index")
async def vault_index(authorization: str | None = Header(None)):
    _verify_key(authorization)
    return [m.model_dump() for m in vault.list_all()]


@app.post("/api/vault/sync", response_model=SyncResponse)
async def vault_sync_receive(
    cid: str = Form(...), filename: str = Form(...),
    mime_type: str = Form(""), file: UploadFile = File(...),
    authorization: str | None = Header(None),
):
    """Receive a synced file from a peer node."""
    _verify_key(authorization)
    data = await file.read()
    if vault.has(cid):
        return SyncResponse(cid=cid, status="already_exists", message="File already in vault.")
    meta = await vault.store(data, filename, mime_type or None)
    if meta.cid != cid:
        return SyncResponse(cid=cid, status="error",
                            message=f"CID mismatch: expected {cid[:16]}…, got {meta.cid[:16]}…")
    return SyncResponse(cid=cid, status="accepted", message="File synced successfully.")


@app.get("/api/vault/diff", response_model=VaultDiffResponse)
async def vault_diff(authorization: str | None = Header(None)):
    _verify_key(authorization)
    return await vault.diff_with_remote()


@app.get("/api/vault/{cid}")
async def vault_download(cid: str, authorization: str | None = Header(None)):
    _verify_key(authorization)
    try:
        data, meta = await vault.retrieve(cid)
    except FileNotFoundError:
        raise HTTPException(404, f"CID {cid[:16]}… not found.")
    return Response(
        content=data,
        media_type=meta.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{meta.filename}"'},
    )


# ═══════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════

@app.get("/api/models")
async def list_models():
    """List available Ollama models."""
    return {"models": await brain.list_models(), "current": brain.local.model}


@app.post("/api/models/select")
async def select_model(name: str = Form(...), authorization: str | None = Header(None)):
    """Switch the active local model."""
    _verify_key(authorization)
    brain.select_model(name)
    logger.info(f"Model switched to '{name}'")
    return {"status": "ok", "model": name}


# ═══════════════════════════════════════════════════
# Logs
# ═══════════════════════════════════════════════════

@app.get("/api/logs")
async def get_logs():
    """Return recent log entries for the terminal UI."""
    return {"logs": get_log_buffer().snapshot()}


# ═══════════════════════════════════════════════════
# Pulse
# ═══════════════════════════════════════════════════

@app.get("/api/pulse", response_model=HeartbeatResponse)
async def pulse_endpoint(authorization: str | None = Header(None)):
    _verify_key(authorization)
    return pulse.get_status(vault_file_count=vault.file_count)


# ═══════════════════════════════════════════════════
# Entrypoint
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.routes:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
        log_level="info",
    )
