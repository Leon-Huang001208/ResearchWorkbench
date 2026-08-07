# 系统中心资源监控交付报告

日期：2026-08-07
范围：`codex/system-center-ui` 分支的系统中心资源与配置导航 UI；本报告仅记录该分支，不合并 `master`。

## 改动范围

| 类别 | 文件 | 说明 |
| --- | --- | --- |
| 前端 | `app/web/templates/index.html` | 侧栏唯一“系统”入口、资源/配置页内标签、异常筛选浮层 DOM。 |
| 前端 | `app/web/static/js/app.js` | 将旧 `resource-monitor`/`config` 本地导航迁移到 `system` 与受限子标签；按真实子标签启动或停止采样。 |
| 前端 | `app/web/static/js/resource-monitor.js` | 正常状态隐藏成功徽标；仅显示待处理异常或采样不可用；深色单选筛选器支持键盘、外部点击和 `Escape`。 |
| 前端 | `app/web/static/style.css` | 系统中心标签、紧凑异常行、筛选浮层及窄屏样式。 |
| 测试 | `tests/unit/test_resource_monitor_frontend_static.py`、`tests/unit/test_setup_wizard_frontend_static.py` | 覆盖系统入口、旧路由迁移、资源轮询生命周期与可访问筛选器契约。 |
| 文档 | `docs/modules/app_web.md`、`docs/REFERENCE.md`、`docs/FILE_GUIDE.md`、`docs/CHANGELOG.md` | 记录单一系统入口、状态语义、筛选/紧凑事件、路由迁移与隔离预览边界。 |

## 实际验证

| 命令 / 检查 | 结果 |
| --- | --- |
| `python -m pytest tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_setup_wizard_frontend_static.py tests/unit/test_configuration_frontend_static.py -q` | 通过：59 passed（0.42s）。 |
| `node --check app/web/static/js/app.js` | 通过。 |
| `node --check app/web/static/js/resource-monitor.js` | 通过。 |
| `ruff check tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_setup_wizard_frontend_static.py tests/unit/test_configuration_frontend_static.py` | 通过：`All checks passed!`。 |
| `git diff --check` 与 `git diff --check master...HEAD` | 通过。 |
| `npm run desktop:preview -- --port 8766 --use-stable-data` | 已启动隔离预览；Tauri dev 编译完成并启动窗口，日志确认后端 `127.0.0.1:8766` ready。 |
| `curl http://127.0.0.1:8766/health` | 200，返回 `status: ok`、数据库 `ready`。 |
| HTML 只读检查 | 200；确认 `data-section="system"`、两个 `data-system-tab`、`resource-filter-menu-status` 和 `resource-monitor-status` 均已输出。 |

## 预览信息

- URL：`http://127.0.0.1:8766/`
- 后端 reloader PID：8410；后端 server PID：8421（以 `lsof -iTCP:8766 -sTCP:LISTEN` 实测）。
- 预览使用 `--use-stable-data`，但 `ALPHAFOUNDRY_PREVIEW=1` 已由启动器设置；日志确认跳过数据库初始化及后台服务。它不会替换正式桌面端的 8765 实例。

## 未验证项与风险

- 未在 Windows 原生 CI 或真实 Windows 安装环境验证；本地 macOS 预览不能证明 Windows 兼容性。
- 未构建或发布安装包；预览不是正式桌面端、sidecar 或升级验证。
- 仅进行 HTTP/HTML 与桌面壳启动验证，尚待人工在预览窗口验收标签切换、正常/异常/采样不可用状态、筛选器选择和窄屏布局。
- 已将 `style.css`、`app.js` 与 `resource-monitor.js` 的查询版本更新为系统中心版本，并在隔离预览中确认 HTML 返回新引用；仍需在正式桌面端合并后完成一次人工刷新验收。
