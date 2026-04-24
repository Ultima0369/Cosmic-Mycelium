"""
Fossil Layer — 化石层

死亡节点的核心记忆被压缩为只读的"化石"记录，
供新生节点在 DIFFUSE 期内省阶段"考古"。

哲学映射:
  - "跨越灭绝鸿沟" → 化石为新生节点提供连续性
  - "创造性毁灭" → 死亡不是终结，是演化的燃料
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FossilRecord:
    """
    化石记录 — 死而复生的节点留下的只读记忆。

    Attributes:
        node_id: 死亡节点的ID
        death_timestamp: 死亡时间
        lifespan_cycles: 存活周期数
        epitaph: 墓志铭（死亡时的状态摘要）
        core_memories: 最重要的N条记忆路径 {path: strength}
        final_situation: 死亡时的态势向量摘要
        legacy_count: 此化石被后代"考古"的次数
    """

    node_id: str
    death_timestamp: float = field(default_factory=time.time)
    lifespan_cycles: int = 0
    epitaph: str = ""
    core_memories: dict[str, float] = field(default_factory=dict)
    final_situation: dict[str, Any] = field(default_factory=dict)
    legacy_count: int = 0

    def __repr__(self) -> str:
        return (
            f"FossilRecord({self.node_id}, "
            f"lived={self.lifespan_cycles}cyc, "
            f"legacy={self.legacy_count}, "
            f"memories={len(self.core_memories)})"
        )


class FossilLayer:
    """
    化石层 — 存储和管理所有死亡节点的化石记录。

    使用方式:
        layer = FossilLayer()
        layer.bury(record)       # 埋葬一个节点
        fossils = layer.excavate()  # 挖掘所有化石
        layer.dig("node_001")    # 定向挖掘某个化石
    """

    def __init__(self, max_fossils: int = 1000):
        self._records: dict[str, FossilRecord] = {}
        self._max_fossils = max_fossils
        self._total_excavations: int = 0

    def bury(self, record: FossilRecord) -> None:
        """
        埋葬一个死亡节点。

        如果化石数量超过上限，删除最古老的化石以释放空间。
        这是"遗忘"在化石层的对应：即使是死亡，也不能无限堆积。
        """
        if len(self._records) >= self._max_fossils:
            oldest_key = min(self._records.keys(), key=lambda k: self._records[k].death_timestamp)
            del self._records[oldest_key]
            logger.debug("[Fossil] 最古老的化石 %s 已被覆盖", oldest_key)

        self._records[record.node_id] = record
        logger.info(
            "[Fossil] %s 被埋葬 (活了 %d 周期，留下 %d 条核心记忆)",
            record.node_id, record.lifespan_cycles, len(record.core_memories),
        )

    def excavate(self, sort_by: str = "death_timestamp") -> list[FossilRecord]:
        """
        挖掘所有化石，供新生节点"考古"。

        Args:
            sort_by: 排序方式 (death_timestamp / lifespan_cycles / legacy_count)

        Returns:
            排序后的化石记录列表
        """
        records = list(self._records.values())
        if sort_by == "lifespan_cycles":
            records.sort(key=lambda r: -r.lifespan_cycles)
        elif sort_by == "legacy_count":
            records.sort(key=lambda r: -r.legacy_count)
        else:
            records.sort(key=lambda r: -r.death_timestamp)

        for r in records:
            r.legacy_count += 1
        self._total_excavations += len(records)

        return records

    def dig(self, node_id: str) -> FossilRecord | None:
        """定向挖掘特定节点的化石。"""
        record = self._records.get(node_id)
        if record:
            record.legacy_count += 1
            self._total_excavations += 1
        return record

    def get_status(self) -> dict[str, Any]:
        """化石层状态报告。"""
        return {
            "fossil_count": len(self._records),
            "max_fossils": self._max_fossils,
            "total_excavations": self._total_excavations,
            "oldest_fossil": min(
                (r.node_id for r in self._records.values()),
                default=None,
            ),
            "most_excavated": max(
                ((r.node_id, r.legacy_count) for r in self._records.values()),
                key=lambda x: x[1],
                default=(None, 0),
            ),
        }
