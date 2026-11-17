# WE-Learn-Assistant

基于模块化 Python 架构的 WE Learn 学习辅助与学习记录管理框架。

> [!IMPORTANT]
> 本项目仅用于合规的学习辅助、课程结构整理、学习资料组织与设备/页面状态诊断。严禁用于伪造学习时长、伪造录音与学习记录、自动伪造答题提交或绕过平台权限及成绩验证。

## 核心技术栈

- **桌面界面**：PySide6
- **Web 自动化**：Playwright（Microsoft Edge）
- **Android 自动化**：ADB + UIAutomator
- **数据存储**：SQLite
- **配置管理**：PyYAML
- **测试与规范**：pytest / ruff

## 目录结构

```text
WE-Learn-Assistant/
├── app/desktop/          # PySide6 桌面端主界面与状态页面
├── core/                 # 核心业务模型、SQLite 数据层、任务调度与日志脱敏
│   ├── course/
│   ├── task/
│   ├── scheduler/
│   └── storage/
├── adapters/             # 平台适配器（Web Edge / Android ADB）
│   ├── web/
│   └── android/
├── modules/              # 专项学习辅助模块（听力、阅读、口语、写作、词汇）
│   ├── listening/
│   ├── reading/
│   ├── speaking/
│   ├── writing/
│   └── vocabulary/
├── analysis/             # 页面结构、网络结构与兼容性分析
│   ├── network/
│   ├── page/
│   └── compatibility/
├── config/               # 配置示例（config.example.yaml）
├── docs/                 # 架构与开发文档
├── tests/                # pytest 自动化测试套件
└── .github/workflows/    # GitHub Actions CI 工作流
```

## 第一阶段能力范围

- 桌面端基础控制台（课程管理、任务管理、设备状态、测试日志、设置）
- SQLite 持久化数据层与基础版本迁移（`Course`、`Chapter`、`Task`、`TaskStatus`、`OperationLog`）
- 统一任务状态机与异常恢复（`pending`、`in_progress`、`completed`、`failed`、`skipped`）
- Web Adapter（Edge 浏览器连接/启动检测、标题/URL 读取、截图、页面结构分析、登录态可见性检查；不自动填写或读取用户凭证）
- Android Adapter（ADB 安装检测、设备状态检测、型号与系统版本读取、前台应用获取、测试截图、诊断报告；不采集 IMEI、设备序列号等非必要标识）
- 日志脱敏与配置隔离

## 快速开始

### 1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 初始化本地配置

```powershell
Copy-Item config/config.example.yaml config/config.yaml
```

### 3. 启动桌面程序

```powershell
python -m app.desktop.main
```

### 4. 运行测试与代码检查

```powershell
ruff check .
pytest
```

## 开源协议

基于 [MIT License](LICENSE) 开源。
