
import base64
import re
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA


_config_cache = {}
_created_dirs = set()
_allowed_accounts_cache = {}


_HTML_PATTERNS = [
    re.compile(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<article[^>]*>(.*?)</article>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<div[^>]*class="rich_media_content"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE),
]

_HTML_CLEANUP_PATTERNS = [
    (re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE), ''),
    (re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE), ''),
    (re.compile(r'<nav[^>]*>.*?</nav>', re.DOTALL | re.IGNORECASE), ''),
    (re.compile(r'<header[^>]*>.*?</header>', re.DOTALL | re.IGNORECASE), ''),
    (re.compile(r'<footer[^>]*>.*?</footer>', re.DOTALL | re.IGNORECASE), ''),
    (re.compile(r'<aside[^>]*>.*?</aside>', re.DOTALL | re.IGNORECASE), ''),
    (re.compile(r'<[^>]+>'), ' '),
]

_HTML_ENTITY_PATTERNS = [
    (re.compile(r'&nbsp;'), ' '),
    (re.compile(r'&lt;'), '<'),
    (re.compile(r'&gt;'), '>'),
    (re.compile(r'&amp;'), '&'),
    (re.compile(r'&quot;'), '"'),
]


def rsa_encrypt(text: str, public_key_pem: str) -> str:
    """使用 RSA 公钥加密文本"""
    if "-----BEGIN PUBLIC KEY-----" not in public_key_pem:
        public_key_pem = "-----BEGIN PUBLIC KEY-----\n" + public_key_pem + "\n-----END PUBLIC KEY-----"
    public_key = RSA.import_key(public_key_pem)
    cipher = PKCS1_v1_5.new(public_key)
    encrypted = cipher.encrypt(text.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def parse_timestamp(report: Dict) -> str:
    """统一处理时间戳解析"""
    timestamp_keys = ['createat', 'publishTime', 'time', 'timestamp']
    timestamp = None
    for key in timestamp_keys:
        if key in report and report[key]:
            timestamp = report[key]
            break

    if not timestamp:
        return ''

    try:
        ts = int(timestamp)
        if ts > 9999999999:
            ts = ts / 1000
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return ''


def ensure_dir(path: str):
    """确保目录存在，使用缓存避免重复系统调用"""
    if path in _created_dirs:
        return
    os.makedirs(path, exist_ok=True)
    _created_dirs.add(path)


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件，使用缓存避免重复读取"""
    global _config_cache

    if config_path in _config_cache:
        return _config_cache[config_path]

    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        _config_cache[config_path] = config
        return config
    except ImportError:
        return {}
    except Exception:
        return {}


def setup_logger(
    name: str,
    output_dir: str,
    starttime: str,
    log_level: int = logging.INFO
) -> logging.Logger:
    """设置日志记录器，避免重复添加 handler"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}_{starttime}.log"

    logger.setLevel(log_level)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger


def extract_text_from_html(html: str) -> str:
    """从 HTML 中提取纯文本内容，使用预编译正则表达式"""
    if not html:
        return ""

    content = ""
    for pattern in _HTML_PATTERNS:
        matches = pattern.findall(html)
        if matches:
            content = max(matches, key=len)
            if len(content) > 100:
                break

    if not content:
        content = html

    for pattern, replacement in _HTML_CLEANUP_PATTERNS:
        content = pattern.sub(replacement, content)

    for pattern, replacement in _HTML_ENTITY_PATTERNS:
        content = pattern.sub(replacement, content)

    lines = [line.strip() for line in content.split('\n') if line.strip()]
    content = '\n'.join(lines)
    content = re.sub(r'[ \t]+', ' ', content)
    content = re.sub(r'\n\s*\n', '\n', content)

    return content.strip()


def clean_unwanted_content(text: str) -> str:
    """清理无关内容"""
    if not text:
        return ""

    filter_keywords = [
        '首页', '看研报', '资讯聚合', '个人订阅', '自选股', '会议日历',
        '全部消息', '全部标记为已读', '消息中心', '收藏笔记', '个人中心',
        '权限', '关于', '退出', '字号', 'A+', '标准', 'A-', '收藏', '笔记',
        '我的笔记', '剩余字数', '保存', '关闭', '原文链接', '关注', '实体识别',
        '全部', 'A股', '非A股', '产品概念', '发债', '实体联想', '关系图谱',
        '全屏打开', '暂无数据', '选择右边实体', '最大层数', '筛选', '公司图谱',
        '展示所有', '确定要删除', '删除', '取消', '添加收藏', '创建收藏夹',
        '收藏夹', '知丘智能资讯平台', '用户协议', '隐私政策', '用户管理规则',
        '客服电话', '阅读历史', '最近阅读', '更多', '扫描二维码', '客户经理',
        '手机号', '提示', '确定', '确认', '朗读', 'stop', 'repeat', 'max volume',
        'drownMenu', '{{', '}}',
        '往期推荐', '往期精彩', '推荐阅读', '长按加微信', '商务合作',
        '喜欢', '分享本文', '点赞', '在看', 'AI帮你提炼', '看完要点',
    ]

    lines = text.split('\n')
    cleaned_lines = []
    skip_mode = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        for section_start in ['往期推荐', '往期精彩', '推荐阅读']:
            if section_start in line:
                skip_mode = True
                break

        if skip_mode:
            continue

        skip = False
        for kw in filter_keywords:
            if kw in line:
                skip = True
                break

        if len(line) < 2 and not any('一' <= c <= '鿿' for c in line):
            skip = True

        if not skip:
            cleaned_lines.append(line)

    cleaned_text = '\n'.join(cleaned_lines)
    cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)

    return cleaned_text

