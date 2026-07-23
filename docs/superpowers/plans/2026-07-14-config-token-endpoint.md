# Config Token Endpoint 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `GET /api/config/token` 端点，前端启动时动态拉取进程 token，彻底消除后端重启导致系统配置页 403 的问题。

**Architecture:** 后端新增一个只校验 Origin/Host（不校验 token）的端点，返回当前进程的 CSRF token。前端在 `initConfigurationPage()` 前先 fetch 该端点，将拿到的 token 写入内存变量，后续所有 `/api/config` 请求从内存读 token 而不从 meta 标签读。meta 标签保留作降级（未来可去掉）。

**Tech Stack:** Python 3.11 + FastAPI、原生 ES Module JS（无框架）、pytest

---

## 文件变更地图

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `app/api/configuration_security.py` | **修改** | 新增 `require_configuration_origin_only` 依赖（只校验 Origin/Host，不校验 token） |
| `app/api/routes/configuration.py` | **修改** | 新增 `GET /api/config/token` 路由，使用新依赖 |
| `app/web/static/js/configuration.js` | **修改** | 新增 `fetchConfigToken()` + 内存 token 缓存；`configurationRequestOptions` 优先从内存读 token |
| `tests/unit/app/api/routes/test_configuration_token.py` | **新建** | 后端 token 端点的单元测试 |
| `tests/unit/app/api/test_configuration_security.py` | **新建** | `require_configuration_origin_only` 的单元测试 |

---

## Task 1：后端安全依赖 — `require_configuration_origin_only`

**Files:**
- Modify: `app/api/configuration_security.py`
- Test: `tests/unit/app/api/test_configuration_security.py`

- [ ] **Step 1: 新建测试文件，写失败测试**

```python
# tests/unit/app/api/test_configuration_security.py
"""require_configuration_origin_only 依赖的单元测试"""
import pytest
from fastapi import HTTPException

from app.api.configuration_security import require_configuration_origin_only


class TestRequireConfigurationOriginOnly:
    """只校验 Origin/Host，不校验 CSRF token"""

    def test_no_origin_passes(self):
        """无 Origin 头时（同源 Tauri 请求）应通过"""
        # 不应抛出异常
        require_configuration_origin_only(origin=None)

    def test_localhost_origin_passes(self):
        """localhost origin 应通过"""
        require_configuration_origin_only(origin="http://localhost:8765")

    def test_127_origin_passes(self):
        """127.0.0.1 origin 应通过"""
        require_configuration_origin_only(origin="http://127.0.0.1:8765")

    def test_tauri_origin_passes(self):
        """Tauri 本地 origin 应通过"""
        require_configuration_origin_only(origin="tauri://localhost")

    def test_external_origin_forbidden(self):
        """外部 origin 应返回 403"""
        with pytest.raises(HTTPException) as exc_info:
            require_configuration_origin_only(origin="https://evil.example.com")
        assert exc_info.value.status_code == 403

    def test_arbitrary_http_origin_forbidden(self):
        """任意非白名单 http origin 应返回 403"""
        with pytest.raises(HTTPException) as exc_info:
            require_configuration_origin_only(origin="http://192.168.1.100:8765")
        assert exc_info.value.status_code == 403
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd d:\Projects\AlphaFoundry
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m pytest tests/unit/app/api/test_configuration_security.py -v
```

预期：`ImportError` 或 `cannot import name 'require_configuration_origin_only'`

- [ ] **Step 3: 在 `configuration_security.py` 末尾添加新依赖函数**

在文件末尾（`require_configuration_csrf_token` 函数之后）追加：

```python
def require_configuration_origin_only(
    origin: Annotated[str | None, Header(alias="Origin")] = None,
) -> None:
    """仅校验 Origin/Host 来源合法性，不校验 CSRF token。
    
    用于 token 分发端点本身——该端点的职责就是颁发 token，
    因此不能要求调用方预先持有 token。
    """
    if origin is not None and not _configuration_origin_is_allowed(origin):
        raise HTTPException(status_code=403, detail="Forbidden")
```

同时在文件顶部的 `__all__` 或导出处（如有）添加该函数名；若无 `__all__`，无需修改。

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m pytest tests/unit/app/api/test_configuration_security.py -v
```

预期：6 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
cd d:\Projects\AlphaFoundry
git add app/api/configuration_security.py tests/unit/app/api/test_configuration_security.py
git commit -m "feat(config): add require_configuration_origin_only dependency for token endpoint"
```

---

## Task 2：后端路由 — `GET /api/config/token`

**Files:**
- Modify: `app/api/routes/configuration.py`
- Test: `tests/unit/app/api/routes/test_configuration_token.py`

- [ ] **Step 1: 新建测试文件，写失败测试**

```python
# tests/unit/app/api/routes/test_configuration_token.py
"""GET /api/config/token 端点的单元测试"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.configuration_security import CONFIGURATION_CSRF_TOKEN
from app.api.routes.configuration import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=True)


class TestGetConfigToken:
    """GET /api/config/token 端点"""

    def test_returns_token_without_csrf_header(self, client):
        """不带 X-AlphaFoundry-Config-Token 也能拿到 token"""
        resp = client.get("/api/config/token")
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token"] == CONFIGURATION_CSRF_TOKEN

    def test_token_is_string(self, client):
        """token 字段是字符串"""
        resp = client.get("/api/config/token")
        assert isinstance(resp.json()["token"], str)
        assert len(resp.json()["token"]) > 16

    def test_external_origin_blocked(self, client):
        """外部 Origin 应被 403 拦截"""
        resp = client.get(
            "/api/config/token",
            headers={"Origin": "https://evil.example.com"},
        )
        assert resp.status_code == 403

    def test_localhost_origin_allowed(self, client):
        """localhost origin 可以拿到 token"""
        resp = client.get(
            "/api/config/token",
            headers={"Origin": "http://localhost:8765"},
        )
        assert resp.status_code == 200

    def test_existing_config_get_still_requires_csrf(self, client):
        """原有 GET /api/config 没有 token 还是 403"""
        resp = client.get("/api/config")
        assert resp.status_code == 403
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m pytest tests/unit/app/api/routes/test_configuration_token.py -v
```

预期：`FAILED` — `GET /api/config/token` 返回 404（路由不存在）

- [ ] **Step 3: 在 `configuration.py` 中添加新路由**

在 `get_configuration` 函数之前插入新端点。同时在 import 部分补充 `require_configuration_origin_only`：

在文件顶部 import 块修改：

```python
from app.api.configuration_security import (
    CONFIGURATION_CSRF_TOKEN,
    require_configuration_csrf_token,
    require_configuration_origin_only,
)
```

在 `router` 定义之后、`get_configuration_service` 之前插入：

```python
@router.get("/token", dependencies=[Depends(require_configuration_origin_only)])
def get_config_token() -> dict[str, str]:
    """颁发当前进程的配置 CSRF token。
    
    只校验 Origin/Host，无需预先持有 token。
    前端启动时调用此端点，将 token 存入内存，
    后续所有 /api/config 请求从内存读取，避免后端重启 token 失效。
    """
    return {"token": CONFIGURATION_CSRF_TOKEN}
```

**注意**：`/token` 路由必须在 `/{section}` 路由之前定义，否则 FastAPI 会将 `token` 当作 section 参数匹配。

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m pytest tests/unit/app/api/routes/test_configuration_token.py -v
```

预期：5 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/configuration.py tests/unit/app/api/routes/test_configuration_token.py
git commit -m "feat(config): add GET /api/config/token endpoint for dynamic token fetch"
```

---

## Task 3：前端 — 动态 token 拉取与内存缓存

**Files:**
- Modify: `app/web/static/js/configuration.js`

> 前端无自动化测试框架，用手动验证步骤替代。

- [ ] **Step 1: 在 `configuration.js` 顶部（`import` 之后、常量之前）添加内存 token 变量和 fetch 函数**

在第 1 行 `import` 之后、第 3 行 `const rowOriginalNames` 之前插入：

```js
let _configToken = null;

async function fetchConfigToken() {
    try {
        const resp = await fetch('/api/config/token', { cache: 'no-store' });
        if (!resp.ok) return;
        const data = await resp.json();
        if (typeof data.token === 'string' && data.token.length > 0) {
            _configToken = data.token;
        }
    } catch {
        // 静默失败，降级到 meta 标签
    }
}
```

- [ ] **Step 2: 修改 `configurationRequestOptions` 优先从内存读 token**

将现有的 `configurationRequestOptions` 函数（第 12-23 行）替换为：

```js
export function configurationRequestOptions(options = {}) {
    const metaToken = globalThis.document
        ?.querySelector('meta[name="alphafoundry-config-token"]')
        ?.content || '';
    const csrfToken = _configToken || metaToken;
    return {
        ...options,
        headers: {
            ...(options.headers || {}),
            'X-AlphaFoundry-Config-Token': csrfToken,
        },
    };
}
```

- [ ] **Step 3: 修改 `initConfigurationPage` 在初始化前先拉取 token**

将现有的 `initConfigurationPage` 函数（文件末尾附近）替换为：

```js
export async function initConfigurationPage() {
    if (!document.getElementById('section-config')) return;
    bindConfigurationEvents();
    if (configurationInitialized) return;
    configurationInitialized = true;
    await fetchConfigToken();
    await loadConfiguration();
}
```

- [ ] **Step 4: 更新版本号防止浏览器缓存旧 JS**

将第 1 行的版本号 bump：

```js
import { apiCall } from './core.js?v=20260714config1';
```

同时在 [index.html](app/web/templates/index.html) 中同步更新 app.js 的版本号（第 2155 行附近）：

```html
<script type="module" src="/static/js/app.js?v=20260714config1"></script>
```

以及 app.js 第 26 行的 configuration.js import：

```js
import { initConfigurationPage } from './configuration.js?v=20260714config1';
```

- [ ] **Step 5: 手动验证**

1. 重启后端（杀掉旧进程，重启 `backend_launcher.py --port 8765`）
2. 在 Tauri 应用中按 `Ctrl+Shift+R` 强制刷新
3. 打开 DevTools（`F12`），在 Network 面板过滤 `/api/config/token`，确认：
   - 请求返回 200
   - Response body 包含 `{"token": "..."}` 
4. 再次切换到系统配置页，确认数据正常加载，无"请求失败"提示
5. 再次重启后端，**不刷新页面**，直接切换到系统配置页，确认仍然能正常加载（这是核心验证点）

- [ ] **Step 6: Commit**

```bash
git add app/web/static/js/configuration.js app/web/templates/index.html app/web/static/js/app.js
git commit -m "feat(config): fetch csrf token dynamically on page init, eliminate restart-induced 403"
```

---

## Task 4：运行完整测试套件，确认无回归

- [ ] **Step 1: 运行格式检查**

```bash
cd d:\Projects\AlphaFoundry
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m ruff check app/api/configuration_security.py app/api/routes/configuration.py
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m black app/api/configuration_security.py app/api/routes/configuration.py --check
```

预期：无错误

- [ ] **Step 2: 运行配置相关测试**

```bash
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m pytest tests/unit/app/api/test_configuration_security.py tests/unit/app/api/routes/test_configuration_token.py -v
```

预期：全部 PASS

- [ ] **Step 3: 运行完整测试套件**

```bash
C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe -m pytest tests/ -v --tb=short -q 2>&1 | tail -20
```

预期：新增测试通过，原有测试无回归

- [ ] **Step 4: Commit（如有格式修复）**

```bash
git add -A
git commit -m "chore: fix lint after config token feature"
```

---

## 自检结果

**Spec 覆盖：**
- ✅ 新端点 `GET /api/config/token`，只校验 Origin/Host
- ✅ 前端 `initConfigurationPage` 启动时先 fetch token
- ✅ token 存内存，`configurationRequestOptions` 优先使用
- ✅ meta 标签降级保留
- ✅ 后端重启后前端不刷新页面也能正常工作（Task 3 Step 5 第 5 点验证）

**Placeholder 扫描：** 无 TBD/TODO，所有步骤含完整代码。

**类型一致性：**
- `require_configuration_origin_only` 在 Task 1 定义，Task 2 import 使用，一致
- `CONFIGURATION_CSRF_TOKEN` 已在 `configuration_security.py` 存在，Task 2 直接 import，一致
- `_configToken` 在 Task 3 Step 1 定义，Step 2 和 Step 3 使用，一致
