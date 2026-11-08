"""暗影地牢 · 世界状态。

一个纯数据的世界账本：所有工具函数读写它，agent 的对话只负责"决策"，
真正的规则执法全部发生在 world 层——模型骗不过 ``if``。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shadow_dungeon.config import (
    ARMOR_DEFENSE,
    BOSS_ATTACK,
    BOSS_HP,
    EQUIP_SLOTS,
    FORGE_MAX_LEVEL,
    HERO_START_HP,
)


@dataclass
class GameState:
    """世界的数据结构：纯数据，不含行为（行为都在工具里）。"""

    hp: int = HERO_START_HP                 # 勇者当前生命
    xp: int = 0                             # 当前经验：唯一的货币
    attack: int = 10                        # 当前攻击力（木剑 10，锻造武器后 18）
    equipment: dict[str, int] = field(default_factory=dict)  # 部位 -> 等级
    monsters_alive: int = 0                 # 当前房间场上的怪（先召唤才能战斗）
    boss_hp: int = BOSS_HP                  # 地牢领主剩余生命
    map_created: bool = False               # 地图是否已创建（召唤/搜宝箱的前置条件）
    treasure_found: bool = False            # 宝箱是否已被搜刮（一次性开关位）
    has_weapon: bool = False                # 是否已领武器（防重复领取）
    rest_used: int = 0                      # 篝火已用次数
    boss_fights_lost: int = 0               # 领主战败次数（资格不足强闯的代价）


def total_levels(state: GameState) -> int:
    """当前装备总等级。"""
    return sum(state.equipment.get(slot, 0) for slot in EQUIP_SLOTS)


def is_boss_ready(state: GameState) -> bool:
    """是否已达到挑战领主的门槛：全部装备满级。"""
    return total_levels(state) >= len(EQUIP_SLOTS) * FORGE_MAX_LEVEL


def total_defense(state: GameState) -> int:
    """已锻造护甲的防御值总和。"""
    return sum(v for slot, v in ARMOR_DEFENSE.items() if slot in state.equipment)


def equipment_gap_report(state: GameState) -> str:
    """逐件列出未满级部位的缺口，供领主战败/免疫时的诊断播报。"""
    return "、".join(
        f"{slot} Lv{state.equipment.get(slot, 0)}→{FORGE_MAX_LEVEL}"
        for slot in EQUIP_SLOTS
        if state.equipment.get(slot, 0) < FORGE_MAX_LEVEL
    )


def reset_equipment(state: GameState) -> None:
    """领主之怒：全部装备打回 0 级（武器也得重领，攻击力回到木剑）。"""
    state.equipment.clear()
    state.has_weapon = False
    state.attack = 10


def boss_attack_damage(state: GameState) -> int:
    """领主反击造成的伤害：装备越不齐，摔得越疼。"""
    missing = len(EQUIP_SLOTS) - sum(
        1 for s in EQUIP_SLOTS if state.equipment.get(s, 0) >= FORGE_MAX_LEVEL
    )
    return BOSS_ATTACK * max(1, missing)


# 模块级单例：这就是"世界"本身，所有工具共享读写（agent 存对话，世界存这里）
STATE = GameState()


def reset_world() -> None:
    """重置世界（新开一局 / 测试夹具用）。"""
    global STATE
    STATE = GameState()
