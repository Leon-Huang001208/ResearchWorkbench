# 全自动数据抓取服务部署说明
## 功能说明
全自动定时抓取真实数据源，完全禁止模拟数据，所有数据均来自公开真实渠道：
- ✅ 财联社电报（每15分钟自动抓取最新内容）
- ✅ 中国证券网新闻（每30分钟自动抓取最新证券新闻）
- ✅ 知丘研报（每1小时自动抓取最新行业/公司研报）
- ✅ 股票行情/财务数据（每天收盘后自动更新重点股票数据）
- ✅ 内置完善防爬机制：随机UA、随机请求间隔、失败自动重试、超时控制
- ✅ 自动去重，避免重复入库
- ✅ 自动健康检查，异常告警

## 部署步骤
### 1. 安装依赖
```bash
pip install apscheduler fake-useragent requests python-daemon
```

### 2. 启动web服务（必须先启动，数据抓取服务依赖web接口）
```bash
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### 3. 启动全自动数据抓取服务
#### 前台运行（调试用）
```bash
python auto_ingest_service.py
```

#### 后台守护进程运行（生产环境）
```bash
python auto_ingest_service.py --daemon
```

#### 查看服务运行状态
```bash
ps aux | grep auto_ingest_service
```

#### 停止服务
```bash
pkill -f auto_ingest_service.py
```

## 防爬配置说明
默认防爬参数可根据需求调整，在`auto_ingest_service.py`开头修改：
```python
REQUEST_TIMEOUT = 15  # 请求超时时间（秒）
RETRY_TIMES = 3  # 失败重试次数
MIN_REQUEST_INTERVAL = 1  # 最小请求间隔（秒）
MAX_REQUEST_INTERVAL = 3  # 最大请求间隔（秒）
```

## 定时任务配置
默认调度规则，可根据需求调整：
| 数据源 | 调度频率 | 说明 |
| --- | --- | --- |
| 财联社电报 | 每15分钟 | 抓取最近5小时的最新电报 |
| 中国证券网新闻 | 每30分钟 | 抓取最新证券板块新闻 |
| 知丘研报 | 每1小时 | 抓取最近1天的最新研报 |
| 股票数据 | 每天15:30 | 收盘后更新重点股票行情/财务数据 |
| 健康检查 | 每10分钟 | 检查web服务是否正常运行 |

## 扩展数据源
如需新增其他数据源，只需要在`auto_ingest_service.py`中新增抓取函数，然后添加到调度器即可，示例：
```python
async def ingest_xxx_data():
    """抓取xxx数据源"""
    # 实现抓取逻辑
    pass

# 添加到调度器
scheduler.add_job(ingest_xxx_data, 'interval', minutes=60, id='ingest_xxx')
```

## 日志查看
服务运行日志会输出到控制台，如需持久化日志，启动时重定向即可：
```bash
python auto_ingest_service.py --daemon > /var/log/auto_ingest.log 2>&1
```
