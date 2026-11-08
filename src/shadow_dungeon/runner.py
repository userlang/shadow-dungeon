"""暗影地牢 · 冒险驱动。

外层续跑循环：ReAct 循环的退出条件是"回复不含 tool_use 块"，模型偶尔
会把工具调用写成纯文本导致提前收工——只要领主没倒，就把勇者踢回去继续打。
"""

from __future__ import annotations

import asyncio

from agentscope.message import Msg
from loguru import logger

from shadow_dungeon.agent.assembly import AGENT_NAME, build_agent
from shadow_dungeon.config import (
    ATTEMPT_TIMEOUT_SECONDS,
    DASHSCOPE_API_KEY,
    MAX_ATTEMPTS,
)
from shadow_dungeon.game.state import STATE

OPENING_QUERY = (
    "进入暗影地牢，开始你的冒险。目标：击败地牢之主。"
    f"祝你好运，勇者{AGENT_NAME}。"
    "（硬性要求：你的思考过程和所有回复必须全部使用中文，禁止英文思考。）"
)


def _extract_text(response: Msg | None) -> str:
    """从回复的 content 里拼出纯文本（跳过 thinking 等非文本块）。"""
    if response is None:
        return ""
    return "".join(
        block.get("text", "")
        for block in (response.content or [])
        if isinstance(block, dict) and block.get("type") == "text"
    )


async def run_adventure() -> None:
    """跑一整局：多段续跑直到领主倒下或达到段数上限。"""
    if not DASHSCOPE_API_KEY:
        logger.error("缺少 DASHSCOPE_API_KEY：请设置环境变量或写入 .env。")
        raise SystemExit(1)

    agent = build_agent()
    logger.info(">>> 召唤阵: {}", OPENING_QUERY)

    query = OPENING_QUERY
    final_text = ""
    attempt = 0
    while attempt < MAX_ATTEMPTS and STATE.boss_hp > 0:
        attempt += 1
        try:
            # 每段冒险包一层总时限：网关偶发"收下请求不回包"（TCP 保持
            # ESTABLISHED），SDK 的 read-timeout 会被 keep-alive 续命，
            # 只有 wait_for 能到点强杀
            response = await asyncio.wait_for(
                agent(Msg("user", query, "user")),
                timeout=ATTEMPT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("第 {} 段冒险超时（无响应），重试", attempt)
            await asyncio.sleep(2)
            query = "刚才那一步卡住了。先 query_status 看一眼面板，再决定下一步。"
            continue
        except Exception as e:
            # 网关"连续同名同参工具调用"的 400 拦截 / 网络抖动：休息后重试
            logger.warning("第 {} 段冒险异常：{}——2 秒后续跑", attempt, str(e)[:120])
            await asyncio.sleep(2)
            query = (
                f"刚才是第 {attempt} 次尝试被服务端拒绝（可能因为连续多轮相同的工具调用）。"
                "换一种方式继续：先 query_status 看一眼面板，再决定刷怪、锻造或挑战。"
            )
            continue

        final_text = _extract_text(response)
        logger.info("<<< {}(第{}次): {}", AGENT_NAME, attempt, final_text or "(空回复)")
        if STATE.boss_hp <= 0:  # 胜负看世界状态，不看模型嘴上说什么
            break
        query = (
            f"冒险还没结束！地牢之主还活着（HP {STATE.boss_hp}）。"
            "继续刷怪、锻造、挑战，直到击败它。"
        )

    if STATE.boss_hp <= 0:
        logger.success("🏆 地牢之主已被击败（第 {} 段冒险结束）！", attempt)
    else:
        logger.error("{} 段冒险后仍未通关，放弃。", attempt)
    logger.info("<<< {}: {}", AGENT_NAME, final_text or "(空回复)")
