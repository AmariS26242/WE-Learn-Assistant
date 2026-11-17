"""运行环境兼容性诊断模块。"""

from __future__ import annotations

import platform
from dataclasses import asdict, dataclass
from typing import Any

from adapters.android.adb_adapter import AdbAdapter
from adapters.web.edge_adapter import EdgeAdapter


@dataclass(slots=True)
class CompatibilitySnapshot:
    """本地运行环境兼容性快照。"""

    os_name: str
    python_version: str
    edge_available: bool
    edge_path: str
    adb_installed: bool
    adb_version: str
    android_connected_count: int
    android_device_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CompatibilityChecker:
    """聚合 Python、Edge 与 ADB 环境检查结果。"""

    def __init__(self, edge_adapter: EdgeAdapter, adb_adapter: AdbAdapter) -> None:
        self.edge_adapter = edge_adapter
        self.adb_adapter = adb_adapter

    def collect(self) -> CompatibilitySnapshot:
        edge_check = self.edge_adapter.check_edge_installed()
        adb_report = self.adb_adapter.run_diagnostics()
        return CompatibilitySnapshot(
            os_name=platform.system(),
            python_version=platform.python_version(),
            edge_available=edge_check.available,
            edge_path=edge_check.executable_path,
            adb_installed=adb_report.adb_installed,
            adb_version=adb_report.adb_version,
            android_connected_count=adb_report.connected_count,
            android_device_state=adb_report.device_state,
        )
