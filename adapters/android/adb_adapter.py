"""ADB 设备检测、状态读取、截图与诊断适配器。

隐私与安全边界：
- 仅读取兼容性排查与教学辅助所需的设备状态、型号、Android 版本及当前前台应用。
- 严禁采集 IMEI、完整硬件序列号、MAC 地址、手机号等个人设备标识。
- 对外输出的设备引用均经过脱敏掩码处理。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.config import AndroidConfig
from core.logging_utils import mask_sensitive_text, mask_value


class AdbAdapterError(RuntimeError):
    """ADB 适配器异常。"""


@dataclass(slots=True)
class AdbCheckResult:
    """ADB 工具安装检测结果。"""

    installed: bool
    executable_path: str = ""
    version: str = ""
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AndroidDeviceEntry:
    """脱敏后的设备连接条目。"""

    device_ref: str
    state: str
    _transport_id: str = field(default="", repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {"device_ref": self.device_ref, "state": self.state}


@dataclass(slots=True)
class AndroidDeviceInfo:
    """Android 设备基础信息（不含 IMEI/序列号等敏感标识）。"""

    device_ref: str
    state: str
    manufacturer: str = ""
    model: str = ""
    android_version: str = ""
    sdk_version: str = ""


@dataclass(slots=True)
class ForegroundAppInfo:
    """当前前台应用包名与组件名。"""

    package_name: str = ""
    activity_name: str = ""
    raw_match: str = ""


@dataclass(slots=True)
class AndroidDiagnosticReport:
    """Android 环境诊断报告。"""

    adb_installed: bool
    adb_version: str = ""
    connected_count: int = 0
    device_state: str = "disconnected"
    manufacturer: str = ""
    model: str = ""
    android_version: str = ""
    sdk_version: str = ""
    foreground_package: str = ""
    foreground_activity: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]

_FOCUS_PATTERN = re.compile(r"([a-zA-Z0-9_.]+)/([a-zA-Z0-9_.$]+)")


class AdbAdapter:
    """基于 ADB CLI 的 Android 设备诊断适配器。"""

    def __init__(
        self,
        config: AndroidConfig | None = None,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self.config = config or AndroidConfig()
        self._runner = runner or subprocess.run

    def resolve_adb_path(self) -> str | None:
        """解析可用的 adb 可执行文件路径。"""
        configured = self.config.adb_path or "adb"
        if Path(configured).is_file():
            return str(Path(configured))
        return shutil.which(configured)

    def check_adb_installed(self) -> AdbCheckResult:
        """检测 ADB 是否已安装并可执行。"""
        adb_exe = self.resolve_adb_path()
        if not adb_exe:
            return AdbCheckResult(
                installed=False,
                error_message="未在 PATH 或配置路径中找到 adb 可执行文件",
            )
        try:
            proc = self._run_raw([adb_exe, "version"])
            stdout = proc.stdout.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                stderr = proc.stderr.decode("utf-8", errors="replace").strip()
                return AdbCheckResult(
                    installed=False,
                    executable_path=adb_exe,
                    error_message=mask_sensitive_text(stderr or f"adb version 返回码 {proc.returncode}"),
                )
            first_line = stdout.splitlines()[0] if stdout else ""
            return AdbCheckResult(installed=True, executable_path=adb_exe, version=first_line)
        except Exception as exc:  # noqa: BLE001
            return AdbCheckResult(
                installed=False,
                executable_path=adb_exe,
                error_message=mask_sensitive_text(f"{type(exc).__name__}: {exc}"),
            )

    def list_devices(self) -> list[AndroidDeviceEntry]:
        """读取已连接设备列表并对外部可见标识做脱敏处理。"""
        adb_exe = self._require_adb()
        proc = self._run_raw([adb_exe, "devices"])
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise AdbAdapterError(mask_sensitive_text(stderr or "adb devices 执行失败"))

        stdout = proc.stdout.decode("utf-8", errors="replace")
        devices: list[AndroidDeviceEntry] = []
        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("List of devices") or stripped.startswith("*"):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            raw_target, state = parts[0], parts[1]
            masked_ref = f"device-{len(devices) + 1} ({mask_value(raw_target, 2)})"
            devices.append(
                AndroidDeviceEntry(
                    device_ref=masked_ref,
                    state=state,
                    _transport_id=raw_target,
                )
            )
        return devices

    def get_device_info(self, device: AndroidDeviceEntry | None = None) -> AndroidDeviceInfo:
        """读取设备型号、厂商和 Android 版本（不读取 IMEI/序列号）。"""
        target = device or self._first_ready_device()
        if target is None:
            raise AdbAdapterError("当前没有已就绪（device 状态）的 Android 设备")

        if target.state != "device":
            return AndroidDeviceInfo(device_ref=target.device_ref, state=target.state)

        manufacturer = self._get_prop(target, "ro.product.manufacturer")
        model = self._get_prop(target, "ro.product.model")
        android_version = self._get_prop(target, "ro.build.version.release")
        sdk_version = self._get_prop(target, "ro.build.version.sdk")
        return AndroidDeviceInfo(
            device_ref=target.device_ref,
            state=target.state,
            manufacturer=manufacturer,
            model=model,
            android_version=android_version,
            sdk_version=sdk_version,
        )

    def get_foreground_app(self, device: AndroidDeviceEntry | None = None) -> ForegroundAppInfo:
        """读取当前前台应用包名与 Activity 名。"""
        target = device or self._first_ready_device()
        if target is None or target.state != "device":
            raise AdbAdapterError("当前没有已就绪的 Android 设备，无法读取前台应用")

        window_output = self._shell(target, ["dumpsys", "window"])
        parsed = self._parse_foreground_output(window_output)
        if parsed.package_name:
            return parsed

        activity_output = self._shell(target, ["dumpsys", "activity", "activities"])
        return self._parse_foreground_output(activity_output)

    def capture_screenshot(
        self,
        output_path: str | Path,
        device: AndroidDeviceEntry | None = None,
    ) -> Path:
        """截取设备屏幕测试截图并保存到本地。"""
        target = device or self._first_ready_device()
        if target is None or target.state != "device":
            raise AdbAdapterError("当前没有已就绪的 Android 设备，无法截图")

        adb_exe = self._require_adb()
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        proc = self._run_raw([adb_exe, "-s", target._transport_id, "exec-out", "screencap", "-p"])
        if proc.returncode == 0 and proc.stdout.startswith(b"\x89PNG"):
            dest.write_bytes(proc.stdout)
            return dest

        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise AdbAdapterError(mask_sensitive_text(stderr or "设备截图失败或返回内容非有效 PNG"))

    def run_diagnostics(self) -> AndroidDiagnosticReport:
        """执行完整 Android 环境诊断并生成结构化报告。"""
        adb_check = self.check_adb_installed()
        if not adb_check.installed:
            return AndroidDiagnosticReport(
                adb_installed=False,
                errors=[adb_check.error_message] if adb_check.error_message else ["ADB 未安装"],
            )

        errors: list[str] = []
        try:
            devices = self.list_devices()
        except AdbAdapterError as exc:
            return AndroidDiagnosticReport(
                adb_installed=True,
                adb_version=adb_check.version,
                errors=[str(exc)],
            )

        if not devices:
            return AndroidDiagnosticReport(
                adb_installed=True,
                adb_version=adb_check.version,
                connected_count=0,
                device_state="disconnected",
                errors=["未检测到已连接的 Android 设备（请检查 USB 调试与数据线连接）"],
            )

        ready = next((d for d in devices if d.state == "device"), None)
        primary = ready or devices[0]
        if primary.state != "device":
            return AndroidDiagnosticReport(
                adb_installed=True,
                adb_version=adb_check.version,
                connected_count=len(devices),
                device_state=primary.state,
                errors=[f"检测到设备，但状态为 {primary.state}，请在手机端确认 USB 调试授权"],
            )

        info = AndroidDeviceInfo(device_ref=primary.device_ref, state=primary.state)
        fg = ForegroundAppInfo()
        try:
            info = self.get_device_info(primary)
        except AdbAdapterError as exc:
            errors.append(str(exc))

        try:
            fg = self.get_foreground_app(primary)
        except AdbAdapterError as exc:
            errors.append(str(exc))

        return AndroidDiagnosticReport(
            adb_installed=True,
            adb_version=adb_check.version,
            connected_count=len(devices),
            device_state=primary.state,
            manufacturer=info.manufacturer,
            model=info.model,
            android_version=info.android_version,
            sdk_version=info.sdk_version,
            foreground_package=fg.package_name,
            foreground_activity=fg.activity_name,
            errors=errors,
        )

    def _first_ready_device(self) -> AndroidDeviceEntry | None:
        devices = self.list_devices()
        return next((d for d in devices if d.state == "device"), None)

    def _get_prop(self, device: AndroidDeviceEntry, prop_name: str) -> str:
        return self._shell(device, ["getprop", prop_name]).strip()

    def _shell(self, device: AndroidDeviceEntry, args: list[str]) -> str:
        adb_exe = self._require_adb()
        proc = self._run_raw([adb_exe, "-s", device._transport_id, "shell", *args])
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise AdbAdapterError(mask_sensitive_text(stderr or f"adb shell {' '.join(args)} 失败"))
        return proc.stdout.decode("utf-8", errors="replace")

    def _parse_foreground_output(self, output: str) -> ForegroundAppInfo:
        for line in output.splitlines():
            if not any(
                marker in line
                for marker in ("mCurrentFocus", "mFocusedApp", "topResumedActivity", "mResumedActivity")
            ):
                continue
            match = _FOCUS_PATTERN.search(line)
            if match:
                return ForegroundAppInfo(
                    package_name=match.group(1),
                    activity_name=match.group(2),
                    raw_match=line.strip(),
                )
        return ForegroundAppInfo()

    def _require_adb(self) -> str:
        adb_exe = self.resolve_adb_path()
        if not adb_exe:
            raise AdbAdapterError("ADB 不可用，请确认已安装 Android Platform-Tools 并加入 PATH")
        return adb_exe

    def _run_raw(self, cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
        try:
            return self._runner(
                cmd,
                capture_output=True,
                timeout=self.config.command_timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbAdapterError(f"ADB 命令执行超时（>{self.config.command_timeout_sec}s）") from exc
        except OSError as exc:
            raise AdbAdapterError(mask_sensitive_text(f"ADB 执行异常: {exc}")) from exc
