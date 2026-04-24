"""
Common utilities shared across all scales.
Contains cross-scale fractal types and topological connectors.

核心导出:
    Scale             — 分形层级枚举 (NANO, INFANT, MESH, SWARM)
    MessageEnvelope   — 跨尺度消息信封
    TranslationTable  — 跨层级翻译表
    EchoDetector      — 跨尺度回声探测器
    EchoPattern       — 回声模式 (跨尺度共振检测结果)
    Situation         — 态势向量
"""

from cosmic_mycelium.common.config_manager import ConfigManager
from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.common.fractal import (
    EchoDetector,
    EchoPattern,
    MessageEnvelope,
    Scale,
    TranslationTable,
)
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint
from cosmic_mycelium.common.situation import Situation

__all__ = [
    "ConfigManager",
    "CosmicPacket",
    "EchoDetector",
    "EchoPattern",
    "MessageEnvelope",
    "PhysicalFingerprint",
    "Scale",
    "Situation",
    "TranslationTable",
]
