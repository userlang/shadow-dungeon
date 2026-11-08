"""暗影地牢 · 命令行入口。

用法::

    # 方式一：安装后直接跑
    uv run shadow-dungeon

    # 方式二：模块方式
    uv run python -m shadow_dungeon
"""

from __future__ import annotations

import asyncio
import logging

from loguru import logger

from shadow_dungeon.config import load_dotenv


def _quiet_framework_logging() -> None:
    """压掉 agentscope 内部的英文 WARNING 刷屏（如 Unsupported block type thinking）。"""
    logging.getLogger("as").setLevel(logging.ERROR)


def main() -> None:
    load_dotenv()
    _quiet_framework_logging()

    from shadow_dungeon.runner import run_adventure  # 延迟导入：先读 .env

    asyncio.run(run_adventure())


if __name__ == "__main__":
    main()
