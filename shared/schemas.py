"""
RainbowHole V0 — Shared Schemas
Pydantic models for all inter-node communication.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════

class NodeType(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class BrainMode(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"
    AUTO = "auto"


class SyncDirection(str, Enum):
    PUSH = "push"
    PULL = "pull"


class SyncStatus(str, Enum):
    LOCAL_ONLY = "local_only"
    REMOTE_ONLY = "remote_only"
    SYNCED = "synced"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════
# Inference Schemas
# ═══════════════════════════════════════════════════

class InferenceRequest(BaseModel):
    """Request payload for AI inference."""
    prompt: str = Field(..., min_length=1, description="The user prompt to process")
    model: Optional[str] = Field(None, description="Model override (None = use default)")
    brain_mode: Optional[BrainMode] = Field(None, description="Routing override (auto, local, remote)")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(1024, ge=1, le=8192, description="Max tokens to generate")
    stream: bool = Field(True, description="Enable token-by-token streaming")
    system_prompt: Optional[str] = Field(None, description="System prompt override")
    # TODO Phase 2: Add `context_cids: list[str]` for RAG — inject Vault docs as context


class InferenceChunk(BaseModel):
    """A single streamed token chunk."""
    token: str = Field(..., description="Generated token text")
    finish_reason: Optional[str] = Field(None, description="null until generation ends")
    model: str = Field(..., description="Model that produced this chunk")
    latency_ms: Optional[float] = Field(None, description="Time since request start")


class InferenceResponse(BaseModel):
    """Full (non-streamed) inference response."""
    text: str = Field(..., description="Complete generated text")
    model: str = Field(..., description="Model used for generation")
    tokens_used: int = Field(0, description="Total tokens consumed")
    latency_ms: float = Field(0.0, description="Total generation time in ms")
    provider: str = Field(..., description="'local' or 'remote'")


# ═══════════════════════════════════════════════════
# Vault / Storage Schemas
# ═══════════════════════════════════════════════════

class FileMetadata(BaseModel):
    """Metadata for a content-addressed file."""
    cid: str = Field(..., description="SHA-256 hex digest (Content ID)")
    filename: str = Field(..., description="Original filename")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    timestamp: float = Field(default_factory=time.time, description="Upload UNIX timestamp")
    mime_type: Optional[str] = Field(None, description="MIME type if detected")
    sync_status: SyncStatus = Field(SyncStatus.LOCAL_ONLY, description="Cross-node sync state")


class SyncRequest(BaseModel):
    """Request to sync a file to the peer node."""
    cid: str = Field(..., description="Content ID to sync")
    filename: str = Field(..., description="Original filename")
    mime_type: Optional[str] = Field(None, description="MIME type")
    # File bytes are sent as multipart form data alongside this JSON


class SyncResponse(BaseModel):
    """Response after a sync operation."""
    cid: str
    status: str = Field(..., description="'accepted', 'already_exists', 'error'")
    message: str = ""


class VaultDiffResponse(BaseModel):
    """Diff between local and remote Vault indices."""
    local_only: list[FileMetadata] = Field(default_factory=list)
    remote_only: list[FileMetadata] = Field(default_factory=list)
    synced: list[FileMetadata] = Field(default_factory=list)


# ═══════════════════════════════════════════════════
# Pulse / Health Schemas
# ═══════════════════════════════════════════════════

class GPUInfo(BaseModel):
    """GPU status from nvidia-smi or simulated."""
    name: str = Field("N/A", description="GPU model name")
    utilization_pct: float = Field(0.0, description="GPU utilization %")
    memory_used_mb: float = Field(0.0, description="VRAM used in MB")
    memory_total_mb: float = Field(0.0, description="Total VRAM in MB")
    temperature_c: Optional[float] = Field(None, description="GPU temp °C")
    available: bool = Field(False, description="Whether a GPU was detected")


class HeartbeatResponse(BaseModel):
    """Heartbeat / health-check response from a node."""
    node_id: str = Field(..., description="Unique node identifier")
    node_type: str = Field(..., description="'local' or 'remote'")
    status: str = Field("online", description="'online', 'degraded', 'offline'")
    latency_ms: Optional[float] = Field(None, description="Round-trip latency to peer")
    gpu_info: Optional[GPUInfo] = Field(None, description="GPU status if available")
    uptime_seconds: float = Field(0.0, description="Node uptime")
    brain_mode: str = Field("auto", description="Current inference mode")
    vault_file_count: int = Field(0, description="Number of files in Vault")
    timestamp: float = Field(default_factory=time.time)


class NodeInfo(BaseModel):
    """Static node configuration info."""
    node_type: NodeType
    brain_mode: BrainMode
    vault_path: str
    local_model: str
    vps_url: str
    api_port: int


# ═══════════════════════════════════════════════════
# API Error Schema
# ═══════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: str
    detail: Optional[str] = None
    code: int = 500
