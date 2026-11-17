"""Android Adapter（ADB）单元测试与真机状态检测。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from adapters.android.adb_adapter import AdbAdapter, AdbAdapterError
from core.config import AndroidConfig


def _cp(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=["adb"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_adb_adapter_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("adapters.android.adb_adapter.shutil.which", lambda _cmd: None)
    adapter = AdbAdapter(AndroidConfig(adb_path="nonexistent_adb_binary"))
    check = adapter.check_adb_installed()
    assert check.installed is False
    report = adapter.run_diagnostics()
    assert report.adb_installed is False


def test_adb_adapter_mock_diagnostics_and_privacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("adapters.android.adb_adapter.shutil.which", lambda _cmd: "adb")

    def fake_runner(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[bytes]:
        if cmd[1:] == ["version"]:
            return _cp(stdout=b"Android Debug Bridge version 1.0.41\nVersion 37.0.1\n")
        if cmd[1:] == ["devices"]:
            return _cp(stdout=b"List of devices attached\nSENSITIVE_SERIAL_987654\tdevice\n")
        if "getprop" in cmd:
            prop = cmd[-1]
            mapping = {
                "ro.product.manufacturer": b"Xiaomi\n",
                "ro.product.model": b"23127PN0CC\n",
                "ro.build.version.release": b"14\n",
                "ro.build.version.sdk": b"34\n",
            }
            return _cp(stdout=mapping.get(prop, b"\n"))
        if "dumpsys" in cmd and "window" in cmd:
            return _cp(
                stdout=b"  mCurrentFocus=Window{123 u0 com.sflep.welearn/com.sflep.welearn.MainActivity}\n"
            )
        if "screencap" in cmd:
            return _cp(stdout=b"\x89PNG\r\n\x1a\nfake_png_bytes")
        return _cp(returncode=1, stderr=b"unknown command")

    adapter = AdbAdapter(runner=fake_runner)
    devices = adapter.list_devices()
    assert len(devices) == 1
    # 确认对外暴露的设备引用不泄露完整序列号
    assert "SENSITIVE_SERIAL_987654" not in devices[0].device_ref

    report = adapter.run_diagnostics()
    assert report.adb_installed is True
    assert report.connected_count == 1
    assert report.manufacturer == "Xiaomi"
    assert report.model == "23127PN0CC"
    assert report.android_version == "14"
    assert report.foreground_package == "com.sflep.welearn"
    assert "SENSITIVE_SERIAL_987654" not in str(report.to_dict())

    shot = adapter.capture_screenshot(tmp_path / "android_screen.png")
    assert shot.exists()


def test_adb_adapter_unauthorized_and_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("adapters.android.adb_adapter.shutil.which", lambda _cmd: "adb")

    def fake_runner(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[bytes]:
        if cmd[1:] == ["version"]:
            return _cp(stdout=b"Android Debug Bridge version 1.0.41\n")
        if cmd[1:] == ["devices"]:
            return _cp(stdout=b"List of devices attached\nABC123456\tunauthorized\n")
        return _cp(returncode=1, stderr=b"device unauthorized")

    adapter = AdbAdapter(runner=fake_runner)
    report = adapter.run_diagnostics()
    assert report.device_state == "unauthorized"
    assert report.errors

    with pytest.raises(AdbAdapterError):
        adapter.get_device_info()


def test_real_adb_device_diagnostics_when_connected() -> None:
    """使用本机真实 ADB 检测工具状态；若未连接真机则显式跳过真机验证，不伪造结果。"""
    adapter = AdbAdapter()
    check = adapter.check_adb_installed()
    if not check.installed:
        pytest.skip("本机未安装 ADB，跳过真实 ADB 检测")

    report = adapter.run_diagnostics()
    assert report.adb_installed is True
    if report.connected_count == 0 or report.device_state != "device":
        pytest.skip(f"未检测到已授权的 Android 真机（当前状态: {report.device_state}），真机能力未验证")

    assert report.model != ""
    assert report.android_version != ""
