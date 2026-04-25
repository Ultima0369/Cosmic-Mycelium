"""
GUI Server — Cosmic Mycelium Backend API

基于 FastAPI + WebSocket 的后端服务，为前端提供实时状态监控和操作接口。

使用方式:
    uvicorn gui_server:app --reload --port 8000

API 端点:
    GET  /api/status           — 整体系统状态
    GET  /api/infants         — 所有 MiniInfant 列表
    GET  /api/infants/{id}   — 单个 infant 详细状态
    GET  /api/fractal/messages — 分形消息历史
    GET  /api/fractal/echoes  — 回声探测器状态
    GET  /api/physics/fingerprint — 物理指纹
    WS   /ws/live            — 实时推送状态更新
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cosmic_mycelium import (
    EchoDetector,
    FractalDialogueBus,
    MiniInfant,
    PhysicalFingerprint,
    Scale,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ====================================================================
# Pydantic 响应模型
# ====================================================================


class InfantSummary(BaseModel):
    id: str
    status: str
    energy: float
    confidence: float
    cycle_count: int
    position: float
    momentum: float
    surprise: float
    synergy_score: float
    hidden_reserve: float
    memory_paths: int


class InfantDetail(InfantSummary):
    fingerprint: str
    best_paths: list[tuple[str, float]]
    physics_health: dict[str, Any]
    breath_state: str
    suspend_count: int


class FractalMessage(BaseModel):
    id: str
    source_scale: str
    target_scale: str
    source_id: str
    timestamp: float
    event_type: str
    payload: dict[str, Any]


class EchoPatternResponse(BaseModel):
    signature: str
    echo_count: int
    depth: int
    scales: list[str]
    metadata: dict[str, Any]


class PhysicsFingerprintResponse(BaseModel):
    infant_id: str
    fingerprint: str
    position: float
    momentum: float
    mass: float
    spring_constant: float
    energy: float
    drift: float


class SystemStatus(BaseModel):
    name: str
    is_running: bool
    infant_count: int
    total_cycles: int
    avg_energy: float
    avg_confidence: float
    collective_tension: float
    message_count: int
    echo_count: int


class WebSocketMessage(BaseModel):
    type: str
    data: dict[str, Any]
    timestamp: float


# ====================================================================
# 应用状态
# ====================================================================


@dataclass
class AppState:
    name: str = "cosmic-mycelium"
    is_running: bool = False
    infants: dict[str, MiniInfant] = field(default_factory=dict)
    fractal_bus: FractalDialogueBus = field(
        default_factory=lambda: FractalDialogueBus("api-bus", verbose=False)
    )
    messages: list[dict[str, Any]] = field(default_factory=list)
    start_time: float = 0.0
    total_cycles: int = 0


app_state = AppState()


# ====================================================================
# 模拟运行
# ====================================================================


def run_simulation_loop():
    """在后台线程中运行模拟循环。"""
    if app_state.is_running:
        return
    app_state.is_running = True
    app_state.start_time = time.time()

    def sim_worker():
        cycle = 0
        while app_state.is_running and cycle < 10000:
            for infant in app_state.infants.values():
                if not app_state.is_running:
                    break
                if infant.status == "alive":
                    infant.bee_heartbeat()
                    app_state.total_cycles += 1
                time.sleep(0.05)
            cycle += 1
            if cycle % 10 == 0:
                _broadcast_heartbeat()

    thread = threading.Thread(target=sim_worker, daemon=True)
    thread.start()


def stop_simulation():
    """停止模拟循环。"""
    app_state.is_running = False


# ====================================================================
# WebSocket 连接管理
# ====================================================================


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def send(self, message: WebSocketMessage):
        if not self.active_connections:
            return
        data = message.model_dump_json()
        await asyncio.gather(
            *[ws.send_text(data) for ws in self.active_connections],
            return_exceptions=True,
        )


manager = ConnectionManager()


async def _broadcast_heartbeat():
    """广播心跳消息到所有 WebSocket 客户端。"""
    if not manager.active_connections:
        return

    status_data = _get_system_status()
    msg = WebSocketMessage(
        type="heartbeat",
        data=status_data,
        timestamp=time.time(),
    )
    await manager.send(msg)


# ====================================================================
# 辅助函数
# ====================================================================


def _get_system_status() -> dict[str, Any]:
    if not app_state.infants:
        return {
            "name": app_state.name,
            "is_running": app_state.is_running,
            "infant_count": 0,
            "total_cycles": app_state.total_cycles,
            "avg_energy": 100.0,
            "avg_confidence": 0.7,
            "collective_tension": 0.0,
            "message_count": len(app_state.messages),
            "echo_count": app_state.fractal_bus.echo_detector.total_patterns,
        }

    energies = [i.energy for i in app_state.infants.values()]
    confidences = [i.confidence for i in app_state.infants.values()]
    avg_e = sum(energies) / len(energies) if energies else 100.0
    avg_c = sum(confidences) / len(confidences) if confidences else 0.7

    collective = app_state.fractal_bus.get_collective_situation()
    tension = collective.get("collective_tension", 0.0)

    return {
        "name": app_state.name,
        "is_running": app_state.is_running,
        "infant_count": len(app_state.infants),
        "total_cycles": app_state.total_cycles,
        "avg_energy": round(avg_e, 1),
        "avg_confidence": round(avg_c, 3),
        "collective_tension": round(tension, 3),
        "message_count": len(app_state.messages),
        "echo_count": app_state.fractal_bus.echo_detector.total_patterns,
    }


def _get_infants_list() -> list[InfantSummary]:
    result = []
    for infant in app_state.infants.values():
        result.append(
            InfantSummary(
                id=infant.id,
                status=infant.status,
                energy=infant.energy,
                confidence=infant.confidence,
                cycle_count=infant._cycle_count,
                position=infant.position,
                momentum=infant.momentum,
                surprise=infant.surprise,
                synergy_score=infant._synergy_score,
                hidden_reserve=infant._hidden_energy_reserve,
                memory_paths=len(infant.memory.path_strength),
            )
        )
    return result


def _get_infant_detail(infant_id: str) -> InfantDetail | None:
    infant = app_state.infants.get(infant_id)
    if infant is None:
        return None

    health = infant.physics.get_health()
    breath_state = infant.hic.state.value if hasattr(infant.hic, "state") else "unknown"

    return InfantDetail(
        id=infant.id,
        status=infant.status,
        energy=infant.energy,
        confidence=infant.confidence,
        cycle_count=infant._cycle_count,
        position=infant.position,
        momentum=infant.momentum,
        surprise=infant.surprise,
        synergy_score=infant._synergy_score,
        hidden_reserve=infant._hidden_energy_reserve,
        memory_paths=len(infant.memory.path_strength),
        fingerprint=infant.get_physical_fingerprint(),
        best_paths=infant.memory.best_paths(3),
        physics_health=health,
        breath_state=breath_state,
        suspend_count=infant.hic.suspend_count,
    )


def _get_messages() -> list[FractalMessage]:
    return [
        FractalMessage(
            id=str(i),
            source_scale=m["source_scale"],
            target_scale=m["target_scale"],
            source_id=m["source_id"],
            timestamp=m["timestamp"],
            event_type=m.get("event_type", "unknown"),
            payload=m["payload"],
        )
        for i, m in enumerate(app_state.messages[-50:])
    ]


def _get_echoes() -> list[EchoPatternResponse]:
    echoes = app_state.fractal_bus.echo_detector.get_echoes(min_depth=1)
    return [
        EchoPatternResponse(
            signature=e.signature,
            echo_count=e.echo_count,
            depth=e.depth,
            scales=[s.level_name for s in e.scales_observed],
            metadata=e.metadata or {},
        )
        for e in echoes[:20]
    ]


def _get_fingerprints() -> list[PhysicsFingerprintResponse]:
    result = []
    for infant in app_state.infants.values():
        health = infant.physics.get_health()
        result.append(
            PhysicsFingerprintResponse(
                infant_id=infant.id,
                fingerprint=infant.get_physical_fingerprint(),
                position=infant.position,
                momentum=infant.momentum,
                mass=infant.physics.mass,
                spring_constant=infant.physics.spring_constant,
                energy=infant.energy,
                drift=health.get("avg_drift", 0.0),
            )
        )
    return result


# ====================================================================
# FastAPI 应用
# ====================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_demo_infants()
    yield
    stop_simulation()


def _init_demo_infants():
    """初始化演示用 MiniInfant 实例。"""
    for i in range(3):
        infant_id = f"bee-{i+1:02d}"
        infant = MiniInfant(
            infant_id,
            fractal_bus=app_state.fractal_bus,
            verbose=False,
            energy_max=100.0,
        )
        app_state.infants[infant_id] = infant
        logger.info(f"Initialized demo infant: {infant_id}")

    app_state.fractal_bus.subscribe(
        Scale.MESH,
        lambda msg: app_state.messages.append({
            "source_scale": msg.source_scale.level_name,
            "target_scale": msg.target_scale.level_name,
            "source_id": msg.source_id,
            "timestamp": msg.timestamp,
            "event_type": msg.metadata.get("event_type", "unknown"),
            "payload": msg.payload,
        }),
        name="api-handler",
    )


app = FastAPI(
    title="Cosmic Mycelium API",
    description="Silicon-Based Lifeform Core Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====================================================================
# API 端点
# ====================================================================


@app.get("/api/status", response_model=SystemStatus)
async def get_status():
    """返回整体系统状态。"""
    data = _get_system_status()
    return SystemStatus(**data)


@app.get("/api/infants", response_model=list[InfantSummary])
async def get_infants():
    """返回所有 MiniInfant 列表。"""
    return _get_infants_list()


@app.get("/api/infants/{infant_id}", response_model=InfantDetail)
async def get_infant(infant_id: str):
    """返回单个 infant 详细状态。"""
    detail = _get_infant_detail(infant_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Infant {infant_id} not found")
    return detail


@app.get("/api/fractal/messages", response_model=list[FractalMessage])
async def get_messages(limit: int = 50):
    """返回分形消息历史。"""
    return _get_messages()


@app.get("/api/fractal/echoes", response_model=list[EchoPatternResponse])
async def get_echoes():
    """返回回声探测器状态。"""
    return _get_echoes()


@app.get("/api/physics/fingerprint", response_model=list[PhysicsFingerprintResponse])
async def get_fingerprints():
    """返回物理指纹。"""
    return _get_fingerprints()


class CreateInfantRequest(BaseModel):
    id: str = Field(..., description="Infant ID")
    energy_max: float = Field(100.0, description="Max energy")


@app.post("/api/infants", response_model=dict)
async def create_infant(body: CreateInfantRequest):
    """创建新的 MiniInfant (body 需包含 id 字段)。"""
    infant_id = body.id
    if infant_id in app_state.infants:
        raise HTTPException(status_code=409, detail=f"Infant {infant_id} already exists")
    energy_max = body.energy_max

    infant = MiniInfant(
        infant_id,
        fractal_bus=app_state.fractal_bus,
        verbose=False,
        energy_max=energy_max,
    )
    app_state.infants[infant_id] = infant
    logger.info(f"Created infant: {infant_id}")
    return {"id": infant_id, "status": infant.status}


@app.delete("/api/infants/{infant_id}")
async def delete_infant(infant_id: str):
    """删除指定的 MiniInfant。"""
    if infant_id not in app_state.infants:
        raise HTTPException(status_code=404, detail=f"Infant {infant_id} not found")

    del app_state.infants[infant_id]
    logger.info(f"Deleted infant: {infant_id}")
    return {"id": infant_id, "deleted": True}


@app.post("/api/simulation/start")
async def start_simulation():
    """启动模拟循环。"""
    if not app_state.infants:
        _init_demo_infants()
    run_simulation_loop()
    return {"running": True}


@app.post("/api/simulation/stop")
async def stop_simulation_endpoint():
    """停止模拟循环。"""
    stop_simulation()
    return {"running": False}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket 实时推送状态更新。"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)