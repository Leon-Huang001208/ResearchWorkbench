"""Wind Excel 插件自定义异常"""


class WindError(Exception):
    """Wind 插件通用错误基类"""

    pass


class WindNotConnectedError(WindError):
    """Excel 未运行或 Wind 插件未加载"""

    def __init__(self):
        super().__init__("未检测到运行中的 Excel 或 Wind 插件。\n" "请先启动 Excel 并确保 Wind 插件已加载。")


class WindSessionExpiredError(WindError):
    """Wind 会话过期，需要用户重新登录"""

    def __init__(self):
        super().__init__(
            "Wind 会话已过期。\n" "请在 Excel 中重新登录 Wind 插件：Excel 菜单栏 → Wind → 登录\n" "登录完成后重试当前操作。"
        )


class WindFormulaError(WindError):
    """Wind 公式执行错误（#N/A, #VALUE! 等）"""

    def __init__(self, formula: str, excel_error: str):
        self.formula = formula
        self.excel_error = excel_error
        super().__init__(f"Wind 公式返回错误: {formula} → {excel_error}")


class WindTimeoutError(WindError):
    """Wind 公式执行超时"""

    def __init__(self, formula: str, timeout: float):
        self.formula = formula
        self.timeout = timeout
        super().__init__(f"Wind 公式执行超时 ({timeout}s): {formula}")
