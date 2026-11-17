"""日志与文本敏感信息脱敏工具。"""

from __future__ import annotations

import json
import re
from typing import Any

_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "secret",
    "cookie",
    "cookies",
    "set-cookie",
    "authorization",
    "session",
    "session_id",
    "imei",
    "serial",
    "serialno",
    "android_id",
}

_KV_PATTERN = re.compile(
    r"(?i)\b("
    r"password|passwd|pwd|token|access_token|refresh_token|api_key|apikey|secret|"
    r"cookie|authorization|session_id|imei|serialno|serial"
    r")\b(\s*[:=]\s*)([^\s,;\"']+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._\-+/=]{8,}")
_WIN_USER_PATH_PATTERN = re.compile(r"(?i)([A-Z]:\\Users\\)([^\\/:*?\"<>|\r\n]+)")
_POSIX_USER_PATH_PATTERN = re.compile(r"(/home/|/Users/)([^/\s]+)")


def mask_value(value: str, visible_prefix: int = 2) -> str:
    """对单个敏感字符串进行掩码。"""
    if not value:
        return "***"
    if len(value) <= visible_prefix:
        return "***"
    return f"{value[:visible_prefix]}***"


def mask_sensitive_text(text: str) -> str:
    """对日志文本中的凭据、令牌、设备标识及本机用户路径进行脱敏。"""
    if not text:
        return text
    masked = _BEARER_PATTERN.sub(r"\1 ***", text)
    masked = _KV_PATTERN.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{mask_value(m.group(3))}",
        masked,
    )
    masked = _WIN_USER_PATH_PATTERN.sub(r"\1<user>", masked)
    masked = _POSIX_USER_PATH_PATTERN.sub(r"\1<user>", masked)
    return masked


def mask_sensitive_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """递归对字典中的敏感字段与字符串路径脱敏。"""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in _SENSITIVE_KEYS:
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = mask_sensitive_mapping(value)
        elif isinstance(value, list):
            result[key] = [
                mask_sensitive_mapping(item)
                if isinstance(item, dict)
                else (mask_sensitive_text(item) if isinstance(item, str) else item)
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = mask_sensitive_text(value)
        else:
            result[key] = value
    return result


def safe_json_dumps(data: dict[str, Any] | None) -> str:
    """先脱敏再序列化为 JSON 字符串。"""
    if not data:
        return "{}"
    return json.dumps(mask_sensitive_mapping(data), ensure_ascii=False)
