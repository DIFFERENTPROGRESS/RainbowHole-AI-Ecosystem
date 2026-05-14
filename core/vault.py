"""
RainbowHole V0 — The Vault
Content-Addressable Storage with SHA-256 CIDs and cross-node sync.

TODO Phase 2: Auto-index stored files for RAG (chunk + embed on store).
TODO Phase 3: DHT-based CID routing across swarm nodes.
"""
from __future__ import annotations
import hashlib, json, logging, os, time
from pathlib import Path
from typing import Optional
import aiofiles, aiofiles.os
import httpx
from dotenv import load_dotenv
from shared.schemas import FileMetadata, SyncResponse, SyncStatus, VaultDiffResponse

load_dotenv()
logger = logging.getLogger("rainbowhole.vault")


class ContentAddressableStorage:
    """Proto-IPFS storage: files keyed by SHA-256 hash with JSON index."""

    INDEX_FILE = "_index.json"

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path or os.getenv("VAULT_PATH", "./vault"))
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self._index_path = self.vault_path / self.INDEX_FILE
        self._index: dict[str, dict] = self._load_index()

    # ── Index management ──────────────────────────

    def _load_index(self) -> dict[str, dict]:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt vault index, rebuilding.")
        return {}

    def _save_index(self) -> None:
        self._index_path.write_text(json.dumps(self._index, indent=2), encoding="utf-8")

    # ── Core operations ───────────────────────────

    @staticmethod
    def compute_cid(data: bytes) -> str:
        """SHA-256 content identifier."""
        return hashlib.sha256(data).hexdigest()

    async def store(self, data: bytes, filename: str, mime_type: Optional[str] = None) -> FileMetadata:
        """Store file by content hash. Deduplicates automatically."""
        cid = self.compute_cid(data)
        file_path = self.vault_path / cid

        if not file_path.exists():
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(data)
            logger.info(f"Stored {filename} → {cid[:16]}… ({len(data)} bytes)")
        else:
            logger.info(f"Deduplicated {filename} → {cid[:16]}…")

        meta = FileMetadata(
            cid=cid, filename=filename, size_bytes=len(data),
            timestamp=time.time(), mime_type=mime_type, sync_status=SyncStatus.LOCAL_ONLY,
        )
        self._index[cid] = meta.model_dump()
        self._save_index()
        return meta

    async def retrieve(self, cid: str) -> tuple[bytes, FileMetadata]:
        """Retrieve file bytes + metadata by CID."""
        if cid not in self._index:
            raise FileNotFoundError(f"CID {cid[:16]}… not in vault index.")
        file_path = self.vault_path / cid
        if not file_path.exists():
            raise FileNotFoundError(f"CID {cid[:16]}… in index but file missing on disk.")
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
        return data, FileMetadata(**self._index[cid])

    def list_all(self) -> list[FileMetadata]:
        """List all stored files."""
        return [FileMetadata(**v) for v in self._index.values()]

    async def delete(self, cid: str) -> bool:
        """Remove file + index entry."""
        if cid not in self._index:
            return False
        file_path = self.vault_path / cid
        if file_path.exists():
            await aiofiles.os.remove(str(file_path))
        del self._index[cid]
        self._save_index()
        logger.info(f"Deleted {cid[:16]}…")
        return True

    def has(self, cid: str) -> bool:
        return cid in self._index

    @property
    def file_count(self) -> int:
        return len(self._index)

    # ── Cross-node sync ───────────────────────────

    async def sync_push(self, cid: str, vps_url: Optional[str] = None,
                        api_key: Optional[str] = None) -> SyncResponse:
        """Push a file to the remote node."""
        vps = (vps_url or os.getenv("VPS_URL", "")).rstrip("/")
        key = api_key or os.getenv("API_KEY", "")
        if not vps:
            return SyncResponse(cid=cid, status="error", message="VPS_URL not configured.")

        data, meta = await self.retrieve(cid)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{vps}/api/vault/sync",
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (meta.filename, data, meta.mime_type or "application/octet-stream")},
                    data={"cid": cid, "filename": meta.filename, "mime_type": meta.mime_type or ""},
                )
                resp.raise_for_status()
                result = SyncResponse(**resp.json())
                if result.status == "accepted":
                    self._index[cid]["sync_status"] = SyncStatus.SYNCED.value
                    self._save_index()
                return result
        except httpx.ConnectError as exc:
            return SyncResponse(cid=cid, status="error", message=f"VPS unreachable: {exc}")

    async def sync_pull(self, cid: str, vps_url: Optional[str] = None,
                        api_key: Optional[str] = None) -> Optional[FileMetadata]:
        """Pull a file from the remote node by CID."""
        vps = (vps_url or os.getenv("VPS_URL", "")).rstrip("/")
        key = api_key or os.getenv("API_KEY", "")
        if not vps:
            return None
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(
                    f"{vps}/api/vault/{cid}",
                    headers={"Authorization": f"Bearer {key}"},
                )
                resp.raise_for_status()
                # Response has file bytes; filename in Content-Disposition
                cd = resp.headers.get("content-disposition", "")
                filename = cid[:12]
                if "filename=" in cd:
                    filename = cd.split("filename=")[-1].strip('"')
                data = resp.content
                meta = await self.store(data, filename, resp.headers.get("content-type"))
                self._index[meta.cid]["sync_status"] = SyncStatus.SYNCED.value
                self._save_index()
                return meta
        except httpx.ConnectError:
            logger.error(f"Cannot pull {cid[:16]}… — VPS unreachable.")
            return None

    async def diff_with_remote(self, vps_url: Optional[str] = None,
                                api_key: Optional[str] = None) -> VaultDiffResponse:
        """Compare local index against remote to find missing CIDs."""
        vps = (vps_url or os.getenv("VPS_URL", "")).rstrip("/")
        key = api_key or os.getenv("API_KEY", "")
        if not vps:
            return VaultDiffResponse(local_only=self.list_all())
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{vps}/api/vault/index",
                                        headers={"Authorization": f"Bearer {key}"})
                resp.raise_for_status()
                remote_items = {item["cid"]: item for item in resp.json()}
        except Exception:
            return VaultDiffResponse(local_only=self.list_all())

        local_cids = set(self._index.keys())
        remote_cids = set(remote_items.keys())
        synced_cids = local_cids & remote_cids
        local_only_cids = local_cids - remote_cids
        remote_only_cids = remote_cids - local_cids

        return VaultDiffResponse(
            local_only=[FileMetadata(**self._index[c]) for c in local_only_cids],
            remote_only=[FileMetadata(**remote_items[c]) for c in remote_only_cids],
            synced=[FileMetadata(**self._index[c]) for c in synced_cids],
        )
