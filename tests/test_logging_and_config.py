"""日志脱敏与配置加载测试。"""

from __future__ import annotations

from pathlib import Path

from core.config import load_config
from core.logging_utils import mask_sensitive_mapping, mask_sensitive_text
from core.storage.database import DatabaseManager
from core.storage.models import OperationLog
from core.storage.repositories import OperationLogRepository


def test_mask_sensitive_text_and_mapping() -> None:
    fake_token = "tok_" + "1234567890abcdef"
    raw = (
        rf"Error at C:\Users\DemoPerson\work token={fake_token} "
        "Authorization: Bearer abcdefghijklmnop password=my_secret_pwd imei=861234567890123"
    )
    masked = mask_sensitive_text(raw)
    assert "DemoPerson" not in masked
    assert "<user>" in masked
    assert fake_token not in masked
    assert "abcdefghijklmnop" not in masked
    assert "my_secret_pwd" not in masked
    assert "861234567890123" not in masked

    mapped = mask_sensitive_mapping({"token": "raw_token", "serialno": "SN123456", "safe": "ok"})
    assert mapped["token"] == "***"
    assert mapped["serialno"] == "***"
    assert mapped["safe"] == "ok"


def test_operation_log_repository_auto_masks(tmp_path: Path) -> None:
    db = DatabaseManager(tmp_path / "logs.db")
    db.initialize()
    repo = OperationLogRepository(db)

    created = repo.create(
        OperationLog(action="auth.check", message="cookie=session_xyz_123456"),
        details={"password": "p1", "path": r"C:\Users\Alice\docs"},
    )
    assert "session_xyz_123456" not in created.message
    assert "p1" not in created.details_json
    assert "Alice" not in created.details_json


def test_load_example_config_disables_credential_autofill() -> None:
    cfg = load_config("config/config.example.yaml")
    assert cfg.web.browser == "msedge"
    assert cfg.safety.mask_logs is True
    assert cfg.safety.allow_credential_autofill is False
