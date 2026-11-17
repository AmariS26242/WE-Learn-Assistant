"""基于 ADB 的 Android 设备诊断与辅助适配器。"""

from adapters.android.adb_adapter import (
    AdbAdapter,
    AdbAdapterError,
    AdbCheckResult,
    AndroidDeviceInfo,
    AndroidDiagnosticReport,
    ForegroundAppInfo,
)

__all__ = [
    "AdbAdapter",
    "AdbAdapterError",
    "AdbCheckResult",
    "AndroidDeviceInfo",
    "AndroidDiagnosticReport",
    "ForegroundAppInfo",
]
