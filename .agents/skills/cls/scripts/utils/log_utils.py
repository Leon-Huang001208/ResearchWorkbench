"""日志配置工具模块"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

def setup_logging(
    logger_name: str,
    verbose: bool = True,
    log_to_file: bool = True,
    log_filename: Optional[str] = None,
    log_dir: str = "logs"
) -> logging.Logger:
    """通用日志配置函数"""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # 清除已有的处理器
    logger.handlers.clear()

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出
    if log_to_file:
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(exist_ok=True)

        if log_filename:
            log_file_path = log_dir_path / log_filename
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = log_dir_path / f"{logger_name}_{timestamp}.log"

        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"[log] 日志文件: {log_file_path}")

    return logger
