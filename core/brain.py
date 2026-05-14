"""
RainbowHole V0 — The Brain
Strategy-pattern inference with Local (Ollama) and Remote (VPS SSE) providers.

TODO Phase 2: Inject RAG context from Vault CIDs before inference.
TODO Phase 3: Add PetalsProvider for distributed inference across swarm nodes.
"""
from __future__ import annotations
import json, logging, os, time
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
import httpx, psutil
from dotenv import load_dotenv
from shared.schemas import BrainMode, InferenceChunk, InferenceRequest, InferenceResponse

load_dotenv()
logger = logging.getLogger("rainbowhole.brain")


class InferenceProvider(ABC):
    """Abstract inference backend."""
    @abstractmethod
    async def generate(self, request: InferenceRequest) -> InferenceResponse: ...
    @abstractmethod
    async def stream(self, request: InferenceRequest) -> AsyncGenerator[InferenceChunk, None]: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
    @abstractmethod
    def provider_name(self) -> str: ...


class LocalProvider(InferenceProvider):
    """Local inference via Ollama HTTP API. Memory-guarded for 8GB nodes."""
    def __init__(self, model: Optional[str] = None, ollama_url: Optional[str] = None, max_ram_pct: float = 85.0):
        self.model = model or os.getenv("LOCAL_MODEL", "phi3:mini")
        self.ollama_url = (ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.max_ram_pct = max_ram_pct
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.ollama_url, timeout=120.0)
        return self._client

    def _check_memory(self) -> None:
        ram = psutil.virtual_memory()
        if ram.percent > self.max_ram_pct:
            raise MemoryError(f"RAM at {ram.percent}% (>{self.max_ram_pct}%). Use remote mode.")

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self._check_memory()
        model = request.model or self.model
        client = await self._get_client()
        start = time.monotonic()
        payload = {"model": model, "prompt": request.prompt, "stream": False,
                   "options": {"temperature": request.temperature, "num_predict": request.max_tokens}}
        if request.system_prompt:
            payload["system"] = request.system_prompt
        try:
            resp = await client.post("/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return InferenceResponse(text=data.get("response", ""), model=model,
                                     tokens_used=data.get("eval_count", 0),
                                     latency_ms=round((time.monotonic() - start) * 1000, 2), provider="local")
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Ollama unreachable at {self.ollama_url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ConnectionError(
                f"Ollama error ({exc.response.status_code}) for model '{model}'. "
                f"Is the model pulled? Run: ollama pull {model}"
            ) from exc

    async def stream(self, request: InferenceRequest) -> AsyncGenerator[InferenceChunk, None]:
        self._check_memory()
        model = request.model or self.model
        client = await self._get_client()
        start = time.monotonic()
        payload = {"model": model, "prompt": request.prompt, "stream": True,
                   "options": {"temperature": request.temperature, "num_predict": request.max_tokens}}
        if request.system_prompt:
            payload["system"] = request.system_prompt
        try:
            async with client.stream("POST", "/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    elapsed = round((time.monotonic() - start) * 1000, 2)
                    yield InferenceChunk(token=d.get("response", ""),
                                         finish_reason="stop" if d.get("done") else None,
                                         model=model, latency_ms=elapsed)
                    if d.get("done"):
                        break
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Ollama unreachable at {self.ollama_url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ConnectionError(
                f"Ollama error ({exc.response.status_code}) for model '{model}'. "
                f"Is the model pulled? Run: ollama pull {model}"
            ) from exc

    async def health_check(self) -> bool:
        try:
            c = await self._get_client()
            return (await c.get("/api/tags")).status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Return list of available model names from Ollama."""
        try:
            c = await self._get_client()
            resp = await c.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def select_model(self, name: str) -> None:
        self.model = name
        logger.info(f"LocalProvider model switched to '{name}'")

    def provider_name(self) -> str:
        return f"local/ollama/{self.model}"

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class RemoteProvider(InferenceProvider):
    """Forwards inference to VPS via HTTP + SSE. Exponential backoff on failure."""
    MAX_RETRIES = 3
    BACKOFF_BASE = 0.5

    def __init__(self, vps_url: Optional[str] = None, api_key: Optional[str] = None):
        self.vps_url = (vps_url or os.getenv("VPS_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.vps_url, timeout=120.0,
                                              headers={"Authorization": f"Bearer {self.api_key}"})
        return self._client

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        import asyncio
        client = await self._get_client()
        start = time.monotonic()
        last_err: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES):
            try:
                payload = request.model_dump()
                payload["stream"] = False
                resp = await client.post("/api/inference", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return InferenceResponse(text=data.get("text", ""), model=data.get("model", "remote"),
                                         tokens_used=data.get("tokens_used", 0),
                                         latency_ms=round((time.monotonic() - start) * 1000, 2), provider="remote")
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_err = exc
                await asyncio.sleep(self.BACKOFF_BASE * (2 ** attempt))
            except httpx.HTTPStatusError as exc:
                raise ConnectionError(f"VPS HTTP {exc.response.status_code}: {exc.response.text}") from exc
        raise ConnectionError(f"VPS unreachable at {self.vps_url} after {self.MAX_RETRIES} attempts: {last_err}")

    async def stream(self, request: InferenceRequest) -> AsyncGenerator[InferenceChunk, None]:
        import asyncio
        client = await self._get_client()
        start = time.monotonic()
        payload = request.model_dump()
        payload["stream"] = True
        for attempt in range(self.MAX_RETRIES):
            try:
                async with client.stream("POST", "/api/inference/stream", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[len("data:"):].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            d = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        yield InferenceChunk(token=d.get("token", ""), finish_reason=d.get("finish_reason"),
                                             model=d.get("model", "remote"),
                                             latency_ms=round((time.monotonic() - start) * 1000, 2))
                return
            except (httpx.ConnectError, httpx.ConnectTimeout):
                await asyncio.sleep(self.BACKOFF_BASE * (2 ** attempt))
        raise ConnectionError(f"VPS unreachable at {self.vps_url} after {self.MAX_RETRIES} attempts.")

    async def health_check(self) -> bool:
        try:
            c = await self._get_client()
            return (await c.get("/health", timeout=5.0)).status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return f"remote/vps/{self.vps_url}"

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class BrainRouter:
    """Orchestrates inference routing. auto = remote-first with local fallback.
    TODO Phase 3: Add 'swarm' mode for Petals distributed inference."""
    def __init__(self, mode: Optional[BrainMode] = None):
        raw = mode or os.getenv("BRAIN_MODE", "auto")
        self.mode = BrainMode(raw)
        self.local = LocalProvider()
        self.remote = RemoteProvider()
        logger.info(f"BrainRouter initialized — mode={self.mode.value}")

    def _primary(self, override_mode: Optional[BrainMode] = None) -> InferenceProvider:
        mode = override_mode or self.mode
        if mode == BrainMode.LOCAL:
            return self.local
        if mode == BrainMode.REMOTE:
            return self.remote
        return self.remote  # auto

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        mode = request.brain_mode or self.mode
        logger.info(f"Inference generate: mode={mode} (request={request.brain_mode}, default={self.mode})")
        p = self._primary(mode)
        try:
            return await p.generate(request)
        except (ConnectionError, MemoryError, httpx.HTTPStatusError, Exception) as exc:
            if mode == BrainMode.AUTO:
                fb = self.local if p is self.remote else self.remote
                logger.warning(f"{p.provider_name()} failed: {exc}. Falling back to {fb.provider_name()}.")
                try:
                    return await fb.generate(request)
                except Exception as fb_exc:
                    raise ConnectionError(
                        f"All providers failed. Primary ({p.provider_name()}): {exc} | "
                        f"Fallback ({fb.provider_name()}): {fb_exc}"
                    ) from fb_exc
            raise

    async def stream(self, request: InferenceRequest) -> AsyncGenerator[InferenceChunk, None]:
        mode = request.brain_mode or self.mode
        logger.info(f"Inference stream: mode={mode} (request={request.brain_mode}, default={self.mode})")
        p = self._primary(mode)
        try:
            async for chunk in p.stream(request):
                yield chunk
        except (ConnectionError, MemoryError, httpx.HTTPStatusError, Exception) as exc:
            if mode == BrainMode.AUTO:
                fb = self.local if p is self.remote else self.remote
                logger.warning(f"{p.provider_name()} failed: {exc}. Falling back to {fb.provider_name()}.")
                try:
                    async for chunk in fb.stream(request):
                        yield chunk
                except Exception as fb_exc:
                    raise ConnectionError(
                        f"All providers failed. Primary ({p.provider_name()}): {exc} | "
                        f"Fallback ({fb.provider_name()}): {fb_exc}"
                    ) from fb_exc
            else:
                raise

    async def health(self) -> dict[str, bool]:
        return {"local": await self.local.health_check(), "remote": await self.remote.health_check(), "mode": self.mode.value}

    async def list_models(self) -> list[str]:
        return await self.local.list_models()

    def select_model(self, name: str) -> None:
        self.local.select_model(name)

    async def close(self) -> None:
        await self.local.close()
        await self.remote.close()
