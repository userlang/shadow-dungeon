"""暗影地牢 · 全局配置。

所有可调参数集中在这里：改难度只动这一个文件，游戏逻辑不碰数字。
"""

from __future__ import annotations

import os
from pathlib import Path


def _read_env_file(path: Path) -> None:
    """把单个 .env 文件读进环境变量（已存在的不覆盖）。"""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_dotenv(path: Path | None = None) -> None:
    """把 ``.env`` 里的 KEY=VALUE 读进环境变量（已存在的不覆盖）。

    查找顺序：显式指定路径 → 项目根目录（src/shadow_dungeon/config.py 上两级）→ 当前工作目录。
    找不到就静默跳过。
    """
    candidates = (
        [path]
        if path is not None
        else [
            Path(__file__).resolve().parents[2] / ".env",  # 项目根
            Path.cwd() / ".env",
        ]
    )
    env_path = next((p for p in candidates if p and p.is_file()), None)
    if env_path is not None:
        _read_env_file(env_path)


# ---------------------------------------------------------------------------
# 模型端配置（优先读环境变量，.env 不入库）
# ---------------------------------------------------------------------------

# 模块加载时自动读一次 .env，保证下面的常量能拿到值
load_dotenv()

# 模型 API Key：环境变量 DASHSCOPE_API_KEY 优先，其次项目根/.env
DASHSCOPE_API_KEY: str = os.environ.get("DASHSCOPE_API_KEY", "")

# 模型服务地址（OpenAI 兼容端点）
DASHSCOPE_BASE_URL: str = os.environ.get(
    "DASHSCOPE_BASE_URL",
    "http://api-ai.stage-xy.ktopia.cn:82/v1",
)

# 聊天模型名
DASHSCOPE_CHAT_MODEL: str = os.environ.get("DASHSCOPE_CHAT_MODEL", "qwen3.7-max")

# 模型请求硬超时（秒）：staging 网关偶发"收下请求不回包"，必须靠客户端超时兜底
LLM_TIMEOUT_SECONDS: float = 300.0

# 单段冒险的总时限（秒）：asyncio.wait_for 强杀，防止无限等待
ATTEMPT_TIMEOUT_SECONDS: float = 600.0

# 记忆压缩阈值（token）：低于网关"连续同名同参工具调用"的 400 拦截窗口
COMPRESSION_TRIGGER_THRESHOLD: int = 2500

# 压缩时保留的最近消息条数
COMPRESSION_KEEP_RECENT: int = 4


# ---------------------------------------------------------------------------
# 游戏规则常量（数值配平只动这里）
# ---------------------------------------------------------------------------

# 每级锻造消耗的经验（经济系统的单价）
FORGE_COST: int = 10

# 各护甲部位的防御值：决定"安全期"何时到来
ARMOR_DEFENSE: dict[str, int] = {
    "肩甲": 2,
    "胸甲": 3,
    "鞋子": 1,
    "护腿": 2,
    "腰带": 1,
}

# 全部装备部位：护甲 5 件 + 武器
EQUIP_SLOTS: tuple[str, ...] = tuple(ARMOR_DEFENSE) + ("武器",)

# 每件装备的最高等级（挑战领主的门槛：全部 6 件满级）
FORGE_MAX_LEVEL: int = 10

# 召唤法阵每次召唤的怪物上限：逼出"分批召唤"的计划行为
SPAWN_LIMIT: int = 25

# 单只小怪的生命值（木剑攻 10 → 一刀一只）
MONSTER_HP: int = 8

# 地牢领主的生命值
BOSS_HP: int = 100

# 领主的攻击力：装备未满级时强行挑战的惩罚结算用
BOSS_ATTACK: int = 10

# 勇者初始生命值
HERO_START_HP: int = 50

# 初始武器攻击力
HERO_START_ATTACK: int = 10

# 锻造武器到满级后的攻击力
FORGED_WEAPON_ATTACK: int = 18

# 篝火休息：消耗经验 / 回复血量 / 每局次数上限
REST_COST: int = 5
REST_HEAL: int = 10
REST_MAX: int = 3

# 宝箱奖励：经验结晶的数值
TREASURE_XP: int = 15

# 领主战失败惩罚：装备全部打回 0 级（重新锻造），勇者不阵亡而是逃跑
BOSS_DEFEAT_RESET_EQUIPMENT: bool = True

# 续跑循环的段数上限：防世界状态异常时的死循环
MAX_ATTEMPTS: int = 20
