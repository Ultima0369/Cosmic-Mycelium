"""
Health Checker — Liveness & Readiness Probes
Kubernetes-compatible health check endpoints.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Optional
from aiohttp import web


@dataclass
class HealthChecker:
    """
    HTTP health check server.
    Implements K8s liveness and readiness probes.
    """
    port: int = 8001
    infant: Optional[object] = None  # SiliconInfant (circular import avoided)
    _runner: Optional[web.AppRunner] = None

    async def start(self) -> None:
        """Start health check server."""
        app = web.Application()
        app.router.add_get("/health/live", self._handle_liveness)
        app.router.add_get("/health/ready", self._handle_readiness)
        app.router.add_get("/health", self._handle_combined)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        print(f"Health server listening on :{self.port}")

    async def stop(self) -> None:
        """Stop health check server."""
        if self._runner:
            await self._runner.cleanup()

    async def _handle_liveness(self, request: web.Request) -> web.Response:
        """
        Liveness probe: Is the process alive?
        Always returns 200 if we can respond.
        """
        return web.json_response({"status": "alive"})

    async def _handle_readiness(self, request: web.Request) -> web.Response:
        """
        Readiness probe: Is the infant ready to serve traffic?
        Checks energy > 0 and not in critical error state.
        """
        if self.infant and self.infant.hic.energy > 0:
            return web.json_response({
                "status": "ready",
                "energy": self.infant.hic.energy,
                "breath": self.infant.hic.breath_state.value,
            })
        return web.json_response(
            {"status": "not_ready", "reason": "energy_depleted"},
            status=503,
        )

    async def _handle_combined(self, request: web.Request) -> web.Response:
        """Combined health endpoint."""
        live_resp = await self._handle_liveness(request)
        ready_resp = await self._handle_readiness(request)
        status = 200 if ready_resp.status == 200 else 503
        live_body = json.loads(live_resp.body.decode())
        ready_body = json.loads(ready_resp.body.decode())
        return web.json_response({
            "status": "ok" if status == 200 else "degraded",
            "liveness": live_body,
            "readiness": ready_body,
        }, status=status)
