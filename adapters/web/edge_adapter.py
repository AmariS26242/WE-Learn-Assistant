"""Microsoft Edge 浏览器适配器（基于 Playwright）。

安全边界：
- 仅用于连接/启动检测、读取页面标题与 URL、页面截图、页面结构分析及登录界面可见性检查。
- 严禁自动填写账号密码，严禁读取、持久化或上传用户 Cookie/Token/凭证。
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.config import WebConfig
from core.logging_utils import mask_sensitive_text


class WebAdapterError(RuntimeError):
    """Web 适配器操作异常。"""


@dataclass(slots=True)
class EdgeCheckResult:
    """Edge 浏览器可用性与运行检测结果。"""

    available: bool
    executable_path: str = ""
    launch_ok: bool = False
    browser_version: str = ""
    page_title: str = ""
    current_url: str = ""
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PageStructureSummary:
    """页面结构基础分析结果（仅提取可见结构统计，不含敏感表单值）。"""

    title: str
    url: str
    heading_count: int = 0
    headings: list[str] = field(default_factory=list)
    link_count: int = 0
    button_count: int = 0
    input_count: int = 0
    iframe_count: int = 0
    has_audio: bool = False
    has_video: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LoginVisibilityResult:
    """登录状态与登录表单可见性检查结果（仅只读观察，不读取或填充凭证）。"""

    url: str
    title: str
    login_form_visible: bool
    password_input_visible: bool
    login_button_visible: bool
    likely_logged_in: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_edge_executable() -> str | None:
    """按常见安装位置和 PATH 查找本机 Microsoft Edge 可执行文件。"""
    candidates: list[Path] = []
    for env_key in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env_key)
        if base:
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    for cmd in ("msedge", "msedge.exe", "microsoft-edge", "microsoft-edge-stable"):
        resolved = shutil.which(cmd)
        if resolved:
            return resolved
    return None


class EdgeAdapter:
    """基于 Playwright 的 Edge Web 自动化与诊断适配器。"""

    def __init__(
        self,
        config: WebConfig | None = None,
        *,
        playwright_factory: Any | None = None,
    ) -> None:
        self.config = config or WebConfig()
        self._playwright_factory = playwright_factory
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._owns_browser: bool = False

    @property
    def is_connected(self) -> bool:
        return self._page is not None

    def check_edge_installed(self) -> EdgeCheckResult:
        """仅检查 Edge 可执行文件是否存在，不启动浏览器。"""
        executable = find_edge_executable()
        if not executable:
            return EdgeCheckResult(
                available=False,
                error_message="未检测到 Microsoft Edge 可执行文件",
            )
        return EdgeCheckResult(available=True, executable_path=executable)

    def connect_or_launch(self, *, headless: bool | None = None) -> EdgeCheckResult:
        """若配置了 CDP 端点则优先连接已有 Edge 实例，否则启动 Edge 浏览器。"""
        executable = find_edge_executable()
        use_headless = self.config.headless if headless is None else headless

        try:
            sync_playwright_fn = self._get_playwright_factory()
            self._playwright = sync_playwright_fn().start()

            if self.config.cdp_endpoint:
                self._browser = self._playwright.chromium.connect_over_cdp(self.config.cdp_endpoint)
                self._owns_browser = False
                contexts = getattr(self._browser, "contexts", [])
                self._context = contexts[0] if contexts else self._browser.new_context()
                pages = getattr(self._context, "pages", [])
                self._page = pages[0] if pages else self._context.new_page()
            else:
                launch_kwargs: dict[str, Any] = {"headless": use_headless}
                if executable:
                    launch_kwargs["executable_path"] = executable
                else:
                    launch_kwargs["channel"] = self.config.browser or "msedge"

                self._browser = self._playwright.chromium.launch(**launch_kwargs)
                self._owns_browser = True
                self._context = self._browser.new_context()
                self._page = self._context.new_page()

            self._page.set_default_timeout(self.config.timeout_ms)
            version = str(getattr(self._browser, "version", "") or "")
            return EdgeCheckResult(
                available=bool(executable or version),
                executable_path=executable or "",
                launch_ok=True,
                browser_version=version,
                page_title=self.get_title(),
                current_url=self.get_url(),
            )
        except Exception as exc:  # noqa: BLE001
            self.close()
            return EdgeCheckResult(
                available=bool(executable),
                executable_path=executable or "",
                launch_ok=False,
                error_message=mask_sensitive_text(f"{type(exc).__name__}: {exc}"),
            )

    def navigate(self, url: str) -> tuple[str, str]:
        """导航至指定 URL 并返回 (title, url)。"""
        page = self._require_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
            return self.get_title(), self.get_url()
        except Exception as exc:  # noqa: BLE001
            raise WebAdapterError(
                mask_sensitive_text(f"页面导航失败: {type(exc).__name__}: {exc}")
            ) from exc

    def get_title(self) -> str:
        page = self._require_page()
        return str(page.title() or "")

    def get_url(self) -> str:
        page = self._require_page()
        return str(getattr(page, "url", "") or "")

    def capture_screenshot(self, output_path: str | Path, *, full_page: bool = False) -> Path:
        """截取当前页面截图到指定路径。"""
        page = self._require_page()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            page.screenshot(path=str(target), full_page=full_page)
            return target
        except Exception as exc:  # noqa: BLE001
            raise WebAdapterError(
                mask_sensitive_text(f"页面截图失败: {type(exc).__name__}: {exc}")
            ) from exc

    def analyze_page_structure(self) -> PageStructureSummary:
        """分析当前页面的基础 DOM 结构（标题、链接、按钮、输入框、音视频与 iframe 数量）。"""
        page = self._require_page()
        try:
            stats = page.evaluate(
                """() => {
                    const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
                        .map(el => (el.innerText || '').trim())
                        .filter(Boolean)
                        .slice(0, 15);
                    return {
                        heading_count: document.querySelectorAll('h1, h2, h3').length,
                        headings,
                        link_count: document.querySelectorAll('a').length,
                        button_count: document.querySelectorAll('button, [role="button"]').length,
                        input_count: document.querySelectorAll('input, textarea, select').length,
                        iframe_count: document.querySelectorAll('iframe').length,
                        has_audio: document.querySelectorAll('audio').length > 0,
                        has_video: document.querySelectorAll('video').length > 0,
                    };
                }"""
            )
            return PageStructureSummary(
                title=self.get_title(),
                url=self.get_url(),
                heading_count=int(stats.get("heading_count", 0)),
                headings=[str(h) for h in stats.get("headings", [])],
                link_count=int(stats.get("link_count", 0)),
                button_count=int(stats.get("button_count", 0)),
                input_count=int(stats.get("input_count", 0)),
                iframe_count=int(stats.get("iframe_count", 0)),
                has_audio=bool(stats.get("has_audio", False)),
                has_video=bool(stats.get("has_video", False)),
            )
        except Exception as exc:  # noqa: BLE001
            raise WebAdapterError(
                mask_sensitive_text(f"页面结构分析失败: {type(exc).__name__}: {exc}")
            ) from exc

    def check_login_visibility(self) -> LoginVisibilityResult:
        """只读检查登录表单与密码框可见性，不读取任何输入值或 Cookie。"""
        page = self._require_page()
        url = self.get_url()
        title = self.get_title()
        try:
            visibility = page.evaluate(
                """() => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && rect.width > 0
                            && rect.height > 0;
                    };
                    const pwdInputs = Array.from(document.querySelectorAll('input[type="password"]'));
                    const passwordVisible = pwdInputs.some(isVisible);

                    const loginButtons = Array.from(
                        document.querySelectorAll('button, input[type="submit"], a')
                    ).filter(el => {
                        const text = (el.innerText || el.value || '').trim().toLowerCase();
                        return text.includes('登录') || text.includes('login') || text.includes('sign in');
                    });
                    const loginButtonVisible = loginButtons.some(isVisible);

                    const forms = Array.from(document.querySelectorAll('form'));
                    const formVisible = forms.some(f => isVisible(f) && f.querySelector('input[type="password"]'));

                    return {
                        passwordVisible,
                        loginButtonVisible,
                        formVisible: formVisible || passwordVisible,
                    };
                }"""
            )
            form_visible = bool(visibility.get("formVisible", False))
            pwd_visible = bool(visibility.get("passwordVisible", False))
            btn_visible = bool(visibility.get("loginButtonVisible", False))
            likely_logged_in = bool(url and not url.startswith("about:") and not pwd_visible and not form_visible)
            reason = (
                "检测到可见登录表单或密码输入框，当前处于未登录或待登录界面"
                if (pwd_visible or form_visible)
                else ("当前页面未检测到可见登录框（可能已登录或尚未导航到登录页）")
            )
            return LoginVisibilityResult(
                url=url,
                title=title,
                login_form_visible=form_visible,
                password_input_visible=pwd_visible,
                login_button_visible=btn_visible,
                likely_logged_in=likely_logged_in,
                reason=reason,
            )
        except Exception as exc:  # noqa: BLE001
            raise WebAdapterError(
                mask_sensitive_text(f"登录状态可见性检查失败: {type(exc).__name__}: {exc}")
            ) from exc

    def close(self) -> None:
        """安全释放页面与浏览器连接资源。"""
        try:
            if self._owns_browser and self._browser is not None:
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._owns_browser = False

    def _get_playwright_factory(self) -> Any:
        if self._playwright_factory is not None:
            return self._playwright_factory
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise WebAdapterError("未安装 playwright 依赖，请先执行 pip install -r requirements.txt") from exc
        return sync_playwright

    def _require_page(self) -> Any:
        if self._page is None:
            raise WebAdapterError("Edge 浏览器尚未连接或启动，请先调用 connect_or_launch()")
        return self._page
