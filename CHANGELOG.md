# 更新日志

本文件记录 `WE-Learn-Assistant` 的重要版本变更。

## [0.1.0] - 2026-11-17

### 新增
- 初始化项目模块化目录结构与基础工程配置（`pyproject.toml`、`requirements.txt`、`config/config.example.yaml`）。
- 实现 SQLite 数据层、数据库版本迁移与模型 CRUD（`Course`、`Chapter`、`Task`、`TaskStatus`、`OperationLog`）。
- 实现统一任务状态机、状态流转校验、操作日志记录及异常恢复能力。
- 实现基于 Playwright 的 Edge Web 适配器（连接/启动检测、标题与 URL 读取、页面截图、结构分析、登录可见性检查）。
- 实现基于 ADB 的 Android 适配器（ADB 安装检测、设备状态、型号与 Android 版本读取、前台应用检测、截图与诊断报告）。
- 实现 PySide6 桌面端主窗口及五大基础页面（课程管理、任务管理、设备状态、测试日志、设置）。
- 补齐 `pytest` 单元测试与 GitHub Actions CI 工作流。
