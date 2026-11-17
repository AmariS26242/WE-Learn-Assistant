# 架构说明（第一阶段）

## 分层设计

1. **应用层（`app/desktop`）**：提供 PySide6 桌面图形界面，负责课程展示、任务状态交互、设备检测触发、操作日志查看与本地设置管理。
2. **核心层（`core`）**：
   - `storage`：SQLite 持久化、Schema 版本迁移（`schema_migrations`）与仓储 CRUD。
   - `course`：课程与章节识别整理服务。
   - `task`：统一任务状态机（`pending`、`in_progress`、`completed`、`failed`、`skipped`）、状态流转校验、审计日志与异常/重启恢复。
   - `scheduler`：任务队列调度与统一异常捕获。
   - `logging_utils`：对日志、错误信息及结构化详情中的凭据与本机路径自动脱敏。
3. **适配器层（`adapters`）**：
   - `web`：基于 Playwright 控制或检测 Microsoft Edge，仅读取标题、URL、可见结构与登录表单可见性，禁止读取或填充用户凭证。
   - `android`：基于 ADB 检测工具安装、设备连接、型号/系统版本、前台应用与截图，禁止采集 IMEI/完整设备序列号。
4. **学习辅助与分析层（`modules`、`analysis`）**：提供听力、阅读、口语质量检查、写作、词汇辅助及页面结构/兼容性分析。
