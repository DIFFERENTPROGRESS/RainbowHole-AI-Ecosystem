"""
RainbowHole V0 — The Pulse
Async heartbeat monitor: latency tracking, GPU status, peer health.
"""
from __future__ import annotations
import asyncio, logging, os, platform, shutil, subprocess, time
from collections import deque
from typing import Optional
import httpx
from dotenv import load_dotenv
from shared.schemas import GPUInfo, HeartbeatResponse

load_dotenv()
logger = logging.getLogger("rainbowhole.pulse")

_BOOT_TIME = time.time()


def _query_gpu() -> GPUInfo:
    """Query local GPU via nvidia-smi. Returns simulated data if unavailable."""
    if not shutil.which("nvidia-smi"):
        return GPUInfo(name="N/A (no GPU detected)", available=False)
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        return GPUInfo(
            name=parts[0], utilization_pct=float(parts[1]),
            memory_used_mb=float(parts[2]), memory_total_mb=float(parts[3]),
            temperature_c=float(parts[4]), available=True,
        )
    except Exception as exc:
        logger.debug(f"nvidia-smi failed: {exc}")
        return GPUInfo(name="GPU query failed", available=False)


class HeartbeatMonitor:
    """Async background task pinging the peer node for latency & GPU status."""

    def __init__(self, interval: Optional[int] = None):
        self.interval = int(interval or os.getenv("HEARTBEAT_INTERVAL", "10"))
        self.vps_url = os.getenv("VPS_URL", "").rstrip("/")
        self.api_key = os.getenv("API_KEY", "")
        self.node_type = os.getenv("NODE_TYPE", "local")
        self.node_id = f"{platform.node()}-{self.node_type}"

        # Sliding window for latency jitter
        self._latencies: deque[float] = deque(maxlen=10)
        self._peer_status: str = "unknown"
        self._peer_gpu: Optional[GPUInfo] = None
        self._last_check: float = 0.0
        self._task: Optional[asyncio.Task] = None

    async def _ping_peer(self) -> None:
        """Single heartbeat ping to the peer node."""
        if not self.vps_url:
            self._peer_status = "no_vps_configured"
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                start = time.monotonic()
                resp = await client.get(
                    f"{self.vps_url}/api/pulse",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                latency = round((time.monotonic() - start) * 1000, 2)
                self._latencies.append(latency)
                if resp.status_code == 200:
                    data = resp.json()
                    self._peer_status = "online"
                    gpu_data = data.get("gpu_info")
                    if gpu_data:
                        self._peer_gpu = GPUInfo(**gpu_data)
                else:
                    self._peer_status = "degraded"
        except (httpx.ConnectError, httpx.ConnectTimeout):
            self._peer_status = "offline"
            self._latencies.append(-1)
        except Exception as exc:
            logger.error(f"Heartbeat error: {exc}")
            self._peer_status = "error"
        self._last_check = time.time()

    async def _loop(self) -> None:
        """Background heartbeat loop."""
        while True:
            await self._ping_peer()
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        """Start the background heartbeat task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            logger.info(f"Pulse started — pinging every {self.interval}s")

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Pulse stopped.")

    @property
    def avg_latency(self) -> Optional[float]:
        valid = [l for l in self._latencies if l >= 0]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def last_latency(self) -> Optional[float]:
        if self._latencies and self._latencies[-1] >= 0:
            return self._latencies[-1]
        return None

    def get_status(self, vault_file_count: int = 0) -> HeartbeatResponse:
        """Build a HeartbeatResponse for this node."""
        local_gpu = _query_gpu()
        return HeartbeatResponse(
            node_id=self.node_id, node_type=self.node_type,
            status="online", latency_ms=self.last_latency,
            gpu_info=local_gpu if local_gpu.available else self._peer_gpu,
            uptime_seconds=round(time.time() - _BOOT_TIME, 1),
            brain_mode=os.getenv("BRAIN_MODE", "auto"),
            vault_file_count=vault_file_count,
        )

    @property
    def peer_status(self) -> str:
        return self._peer_status

    @property
    def peer_gpu(self) -> Optional[GPUInfo]:
        return self._peer_gpu
