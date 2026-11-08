"""暗影地牢 · agent 总装。

把模型、格式化器、工具箱、规划本、记忆压缩全部插拔到位。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel
from agentscope.plan import DefaultPlanToHint, PlanNotebook
from agentscope.token import OpenAITokenCounter
from agentscope.tool import Toolkit

from shadow_dungeon.config import (
    COMPRESSION_KEEP_RECENT,
    COMPRESSION_TRIGGER_THRESHOLD,
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_CHAT_MODEL,
    FORGE_MAX_LEVEL,
    LLM_TIMEOUT_SECONDS,
)
from shadow_dungeon.game.tools import (
    challenge_boss,
    create_map,
    create_weapon,
    fight_monsters,
    forge_equipment,
    query_status,
    rest_at_bonfire,
    search_treasure,
    spawn_monsters,
)

AGENT_NAME = "阿爪"

SYS_PROMPT = (
    f"你是 AI 勇者「{AGENT_NAME}」，被召唤进暗影地牢，"
    f"唯一目标：击败地牢之主（HP 100）。"
    "你了解这个世界的法则：击杀一只怪物 +1 经验；锻造升 1 级装备消耗 10 经验，"
    f"每件装备最高 {FORGE_MAX_LEVEL} 级；召唤法阵每次最多拉来 25 只怪。"
    "切记：装备未全部满级就去挑战地牢之主，会被它把全部装备打回 0 级——"
    "但它杀不死你，你会逃回来重新锻造。量入为出，祝你好运。"
    "无论内心思考还是最终作答，请全程使用中文。"
)

GAME_TOOLS = (
    create_map,
    spawn_monsters,
    fight_monsters,
    create_weapon,
    forge_equipment,
    query_status,
    search_treasure,
    challenge_boss,
    rest_at_bonfire,
)


class 游戏摘要Schema(BaseModel):
    """记忆压缩摘要的结构化模型（替换 agentscope 内置 SummarySchema）。

    内置版给 next_steps 硬编码了 max_length=200，中文摘要一超就
    ValidationError 崩局；这里字段名与默认 summary_template 的占位符
    保持一致（task_overview / current_state / important_discoveries /
    next_steps / context_to_preserve），长度约束降级为描述里的软约束。
    """

    task_overview: str = Field(
        description="用户的核心目标与成功标准（≤300字）。\n"
        "用户做过的澄清或附加约束。",
    )
    current_state: str = Field(
        description="目前已完成的进展（≤300字）。\n"
        "已创建/修改/分析的内容、关键产出。",
    )
    important_discoveries: str = Field(
        description="发现的关键规则或约束（≤300字）。\n"
        "已做的决策及理由、遇到的错误与解决方式、尝试过但无效的方案。",
    )
    next_steps: str = Field(
        description="完成剩余任务所需的具体行动（≤200字，务必精炼，只列要点短语）。\n"
        "待解决的阻塞点或问题；多项时按优先级排序。",
    )
    context_to_preserve: str = Field(
        description="必须延续的偏好或风格要求（≤300字）。\n"
        "不易察觉的领域细节、对用户做过的承诺。",
    )


class ChinesePlan(DefaultPlanToHint):
    """把 agentscope 注入的英文 system-hint 换成中文。

    英文上下文是把模型思考带成英文的源头；属性名与占位符不可改动，
    只翻译措辞。
    """

    no_plan: str = (
        "如果用户的任务比较复杂（如写程序、做游戏），或需要多步骤长链路才能完成"
        "（如跨来源调研），你必须先调用 'create_plan' 制定计划；"
        "任务简单则可以直接执行，无需规划。"
    )

    at_the_beginning: str = (
        "当前计划：\n```\n{plan}\n```\n你可以：\n"
        "- 调用 'update_subtask_state'（subtask_idx=0，state='in_progress'）"
        "把第一个子任务标记为进行中，并开始执行；\n"
        "- 如果第一个子任务暂时无法执行，分析原因并推进计划，"
        "例如向用户追问，或调用 'revise_current_plan' 修订计划；\n"
        "- 用户提出与计划无关的请求时，优先完成用户请求，之后再回到计划；\n"
        "- 用户不想继续当前计划时，与用户确认后调用 'finish_plan'。"
    )

    when_a_subtask_in_progress: str = (
        "当前计划：\n```\n{plan}\n```\n"
        "编号 {subtask_idx} 的子任务“{subtask_name}”正在进行中，详情：\n"
        "```\n{subtask}\n```\n你可以：\n"
        "- 继续执行该子任务并拿到结果；\n"
        "- 子任务完成后调用 'finish_subtask' 并给出具体结果；\n"
        "- 需要更多信息时向用户追问；\n"
        "- 必要时调用 'revise_current_plan' 修订计划；\n"
        "- 用户提出与计划无关的请求时，优先完成用户请求，之后再回到计划。"
    )

    when_no_subtask_in_progress: str = (
        "当前计划：\n```\n{plan}\n```\n"
        "前 {index} 个子任务已完成，当前没有进行中的子任务。你可以：\n"
        "- 调用 'update_subtask_state' 把下一个子任务标记为进行中并开始执行；\n"
        "- 需要更多信息时向用户追问；\n"
        "- 必要时调用 'revise_current_plan' 修订计划；\n"
        "- 用户提出与计划无关的请求时，优先完成用户请求，之后再回到计划。"
    )

    at_the_end: str = (
        "当前计划：\n```\n{plan}\n```\n所有子任务已完成。你可以：\n"
        "- 调用 'finish_plan' 并给出结果，然后向用户总结整个过程和结果；\n"
        "- 必要时调用 'revise_current_plan' 修订计划；\n"
        "- 用户提出与计划无关的请求时，优先完成用户请求，之后再回到计划。"
    )


def build_agent() -> ReActAgent:
    """总装：把所有插拔件装配成勇者「阿爪」。"""
    toolkit = Toolkit()
    for tool in GAME_TOOLS:
        toolkit.register_tool_function(tool)

    return ReActAgent(
        name=AGENT_NAME,
        sys_prompt=SYS_PROMPT,
        model=OpenAIChatModel(
            model_name=DASHSCOPE_CHAT_MODEL,
            api_key=DASHSCOPE_API_KEY,
            # 非流式：staging 端点的流式 SSE 会丢块/重块（thinking 碎片化、
            # tool_use 退化成 <function=...> 文本），非流式由服务端整体解析
            stream=False,
            stream_tool_parsing=False,
            client_kwargs={
                "base_url": DASHSCOPE_BASE_URL,
                "timeout": LLM_TIMEOUT_SECONDS,
                "max_retries": 2,
            },
        ),
        formatter=OpenAIChatFormatter(),
        toolkit=toolkit,
        long_term_memory=None,
        long_term_memory_mode="both",
        compression_config=ReActAgent.CompressionConfig(
            enable=True,
            agent_token_counter=OpenAITokenCounter("gpt-4o"),
            # 阈值低于网关"连续同名同参工具调用"的 400 拦截窗口：
            # 压缩会把旧重复轮标记为 compressed 并从请求里剔除
            trigger_threshold=COMPRESSION_TRIGGER_THRESHOLD,
            keep_recent=COMPRESSION_KEEP_RECENT,
            summary_schema=游戏摘要Schema,
        ),
        enable_meta_tool=True,
        # 游戏工具全是写操作且顺序敏感，必须串行
        parallel_tool_calls=False,
        plan_notebook=PlanNotebook(max_subtasks=6, plan_to_hint=ChinesePlan()),
        print_hint_msg=True,
        # 全满级 ≈ 220 轮工具调用（60 次锻造 + 24 批 × 2 + 杂项），
        # 默认 10 轮上限会中途"总结陈词"弃赛
        max_iters=240,
        tts_model=None,
    )
