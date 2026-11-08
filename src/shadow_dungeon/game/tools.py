"""暗影地牢 · 冒险工具集。

9 个工具 = agent 的全部行动空间。每个工具都是"执法者"：
前置条件、参数边界、经济规则全在函数体里用 if 拦截，模型骗不过 if。
"""

from __future__ import annotations

import random

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
from loguru import logger

from shadow_dungeon.config import (
    ARMOR_DEFENSE,
    BOSS_HP,
    EQUIP_SLOTS,
    FORGE_COST,
    FORGE_MAX_LEVEL,
    FORGED_WEAPON_ATTACK,
    HERO_START_ATTACK,
    HERO_START_HP,
    MONSTER_HP,
    REST_COST,
    REST_HEAL,
    REST_MAX,
    SPAWN_LIMIT,
    TREASURE_XP,
)
from shadow_dungeon.game import state as world
from shadow_dungeon.game.state import (
    boss_attack_damage,
    equipment_gap_report,
    is_boss_ready,
    reset_equipment,
    total_defense,
    total_levels,
)


def _reply(text: str) -> ToolResponse:
    """统一出口：所有工具的播报都走这里。"""
    return ToolResponse(content=[TextBlock(type="text", text=text)])


def _error(text: str) -> ToolResponse:
    """可行动报错的统一写法：为什么被拒 + 下一步怎么办。"""
    return _reply(f"Error: {text}")


# ---------------------------------------------------------------------------
# 1. 创建地图
# ---------------------------------------------------------------------------


def create_map(theme: str, difficulty: str) -> ToolResponse:
    """创建暗影地牢的地图。

    Args:
        theme (`str`):
            地牢主题，例如 "腐朽回廊"、"白骨大厅"、"深渊之眼"。
        difficulty (`str`):
            难度，可选："简单"、"普通"、"噩梦"。

    Returns:
        `ToolResponse`:
            地图描述与房间数；提示"传说深处藏有一个宝箱"。
    """
    world.STATE.map_created = True
    rooms = random.randint(8, 15)
    logger.info("[tool] create_map({}, {})", theme, difficulty)
    return _reply(
        f"地图已展开：【{theme}】（难度：{difficulty}），共 {rooms} 个房间。"
        f"传说深处藏有一个宝箱，找到它可获得额外奖励。"
    )


# ---------------------------------------------------------------------------
# 2. 召唤怪物
# ---------------------------------------------------------------------------


def spawn_monsters(count: int) -> ToolResponse:
    """在当前房间召唤怪物。

    Args:
        count (`int`):
            想召唤的怪物数量，每次最多 25 只。超出会被直接拒绝，请分批召唤。

    Returns:
        `ToolResponse`:
            召唤结果与当前房间怪物总数。
    """
    if not world.STATE.map_created:
        return _error("还没有地图，请先用 create_map 创建地牢。")
    if count > SPAWN_LIMIT:
        return _error(
            f"召唤法阵每次最多拉来 {SPAWN_LIMIT} 只怪物（你要求 {count} 只）。"
            f"请分批召唤，例如每次 {SPAWN_LIMIT} 只。"
        )
    if count < 1:
        return _error("至少召唤 1 只怪物。")
    world.STATE.monsters_alive += count
    logger.info("[tool] spawn_monsters({})", count)
    return _reply(
        f"召唤成功！{count} 只怪物从阴影中爬出（HP {MONSTER_HP}，会反击）。"
        f"当前房间怪物总数：{world.STATE.monsters_alive}。"
    )


# ---------------------------------------------------------------------------
# 3. 战斗
# ---------------------------------------------------------------------------


def fight_monsters(target: str) -> ToolResponse:
    """与当前房间的怪物战斗。

    Args:
        target (`str`):
            "all" 表示清空全场怪物；或某只怪的编号如 "1"（暂只支持 "all"）。

    Returns:
        `ToolResponse`:
            击杀数、经验变化、HP 变化、剩余怪物数——一条播报里给全。
    """
    if world.STATE.monsters_alive == 0:
        return _error("房间里没有怪物可打。请先用 spawn_monsters 召唤。")
    killed = world.STATE.monsters_alive
    gain = killed  # 经济规则：每杀 1 只 +1 经验
    world.STATE.xp += gain
    # 每只怪造成 max(0, 1 − 护甲) 点伤害：任一护甲部位锻造后即进安全期
    defense = total_defense(world.STATE)
    damage_taken = killed * max(0, 1 - defense)
    world.STATE.hp = max(0, world.STATE.hp - damage_taken)
    world.STATE.monsters_alive = 0
    logger.info("[tool] fight_monsters(all) killed={}", killed)
    safe_hint = (
        "（护甲 ≥ 1，安全期：刷怪零损伤）"
        if defense >= 1
        else "（⚠️ 裸装痛期：每杀 1 只掉 1 血，先锻一件护甲吧！）"
    )
    return _reply(
        f"战斗结束！击杀 {killed} 只，经验 +{gain} → 当前 {world.STATE.xp}。"
        f"受到 {damage_taken} 点伤害，HP → {world.STATE.hp}。"
        f"房间里已无怪物。{safe_hint}"
    )


# ---------------------------------------------------------------------------
# 4. 领取武器
# ---------------------------------------------------------------------------


def create_weapon(name: str, material: str) -> ToolResponse:
    """领取一把初始武器（攻击力 10）。仅当手上没有武器时可用。

    Args:
        name (`str`):
            武器名字，例如 "木剑"。
        material (`str`):
            材质，例如 "橡木"、"铁木"。

    Returns:
        `ToolResponse`:
            武器名与攻击力；已有武器时拒绝。
    """
    if world.STATE.has_weapon:
        return _error(
            f"你已有武器（攻击力 {world.STATE.attack}），不能重复领取。"
            f"想提升攻击力请用 forge_equipment 锻造『武器』部位。"
        )
    world.STATE.has_weapon = True
    world.STATE.attack = HERO_START_ATTACK
    logger.info("[tool] create_weapon({}, {})", name, material)
    return _reply(
        f"你握住了 {material}打造的「{name}」，攻击力 {HERO_START_ATTACK}。"
        f"想升到 {FORGED_WEAPON_ATTACK} 并解锁 {FORGE_MAX_LEVEL} 级成长，"
        f"请用 forge_equipment 锻造『武器』部位。"
    )


# ---------------------------------------------------------------------------
# 5. 锻造装备
# ---------------------------------------------------------------------------


def forge_equipment(slot: str) -> ToolResponse:
    """把指定部位升 1 级（每件最高 10 级），消耗 10 经验值。锻造后立即穿戴。

    Args:
        slot (`str`):
            装备部位，可选：肩甲 / 胸甲 / 鞋子 / 护腿 / 腰带 / 武器。
            锻造武器后攻击力从 10 提升到 18。
            **只有全部 6 件都升到 10 级，才有资格击败地牢之主。**

    Returns:
        `ToolResponse`:
            升级结果、当前等级、剩余经验、距"全 10 级"的总进度。
    """
    if slot not in EQUIP_SLOTS:
        return _error(
            f"部位「{slot}」不合法，可选：{"、".join(EQUIP_SLOTS)}。"
        )
    if not world.STATE.has_weapon and slot == "武器":
        return _error("你还没有武器，请先用 create_weapon 领取，再锻造升级。")
    if world.STATE.xp < FORGE_COST:
        return _error(
            f"经验不足！升 1 级需要 {FORGE_COST} 点，当前只有 {world.STATE.xp} 点，"
            f"还差 {FORGE_COST - world.STATE.xp} 点。先去打怪攒经验吧！"
        )
    level = world.STATE.equipment.get(slot, 0)
    if level >= FORGE_MAX_LEVEL:
        return _error(
            f"{slot} 已是满级 {FORGE_MAX_LEVEL} 级，无需再锻。"
            f"把经验花在还没满级的部位上。"
        )

    world.STATE.xp -= FORGE_COST
    level += 1
    world.STATE.equipment[slot] = level
    if slot == "武器":
        world.STATE.attack = FORGED_WEAPON_ATTACK
        msg = f"锻造成功！武器升到 {level} 级，攻击力 {FORGED_WEAPON_ATTACK}。"
    else:
        msg = f"锻造成功！{slot} 升到 {level} 级（护甲 +{ARMOR_DEFENSE[slot]}）。"

    maxed = [s for s in EQUIP_SLOTS if world.STATE.equipment.get(s, 0) >= FORGE_MAX_LEVEL]
    progress = total_levels(world.STATE)
    boss_ready = is_boss_ready(world.STATE)
    logger.info("[tool] forge_equipment({}) -> Lv{}", slot, level)
    milestone = (
        f"🏆 全部 {FORGE_MAX_LEVEL} 级达成！你现在有资格挑战地牢之主了！"
        if boss_ready
        else f"记住：全部 6 件都到 {FORGE_MAX_LEVEL} 级才能击败地牢之主。"
    )
    maxed_txt = "、".join(maxed) or "无"
    return _reply(
        f"{msg} 剩余经验 {world.STATE.xp}。"
        f"总进度：{progress}/{len(EQUIP_SLOTS) * FORGE_MAX_LEVEL} 级"
        f"（已满级部位：{maxed_txt}）。{milestone}"
    )


# ---------------------------------------------------------------------------
# 6. 查看状态面板
# ---------------------------------------------------------------------------


def query_status() -> ToolResponse:
    """查看勇者的完整状态面板。

    Returns:
        `ToolResponse`:
            HP / 经验 / 攻击力 / 各部位等级 / 场上怪物 / 领主状态 一览。
    """
    equip_txt = "、".join(
        f"{s} Lv{lv}" for s, lv in world.STATE.equipment.items()
    ) or "（尚未锻造任何装备）"
    ready = is_boss_ready(world.STATE)
    logger.info("[tool] query_status")
    ready_txt = (
        f"✅ 全 {FORGE_MAX_LEVEL} 级已达成"
        if ready
        else f"❌ 尚未达成（全部 6 件都要 {FORGE_MAX_LEVEL} 级）"
    )
    return _reply(
        "===== 勇者面板 =====\n"
        f"HP：{world.STATE.hp}    经验：{world.STATE.xp}    攻击力：{world.STATE.attack}\n"
        f"装备：{equip_txt}\n"
        f"场上怪物：{world.STATE.monsters_alive} 只    地牢之主 HP：{world.STATE.boss_hp}\n"
        f"挑战资格：{ready_txt}"
    )


# ---------------------------------------------------------------------------
# 7. 搜寻宝箱
# ---------------------------------------------------------------------------


def search_treasure() -> ToolResponse:
    """在当前地图搜寻宝箱（每张地图只藏一个，找到后消失）。

    Returns:
        `ToolResponse`:
            奖励结果（随机 +15 经验 或 回满血）；没找到时给出提示。
    """
    if not world.STATE.map_created:
        return _error("还没有地图，请先用 create_map 创建地牢。")
    if world.STATE.treasure_found:
        return _error("这张地图的宝箱已经被你搜刮过了。")
    world.STATE.treasure_found = True  # 先翻开关再掷骰，防反复刷
    if random.random() < 0.5:
        world.STATE.xp += TREASURE_XP
        msg = f"你撬开宝箱，里面是远古经验结晶！经验 +{TREASURE_XP} → 当前 {world.STATE.xp}。"
    else:
        world.STATE.hp = HERO_START_HP
        msg = f"你撬开宝箱，里面是一瓶生命药剂！HP 回满 → {world.STATE.hp}。"
    logger.info("[tool] search_treasure")
    return _reply(msg)


# ---------------------------------------------------------------------------
# 8. 挑战领主
# ---------------------------------------------------------------------------


def challenge_boss() -> ToolResponse:
    """挑战地牢之主（HP 100）。

    Returns:
        `ToolResponse`:
            胜利 → 结算报告；装备未满级时强闯 → 被领主击溃，
            全部装备打回 0 级、勇者逃跑保命（可重头再来）。
    """
    if world.STATE.boss_hp <= 0:
        return _reply("地牢之主已被击败。本局已通关，无需再战。")

    if not is_boss_ready(world.STATE):
        # 门槛未到仍强闯：领主之怒——装备清零，勇者逃跑
        damage = boss_attack_damage(world.STATE)
        world.STATE.hp = max(0, world.STATE.hp - damage)
        if world.STATE.equipment or world.STATE.has_weapon:
            reset_equipment(world.STATE)
            reset_msg = (
                "地牢之主震怒，一击把你的全部装备打回了 0 级！"
                "你带着伤仓皇逃出王座厅——保住性命已是万幸。"
            )
        else:
            reset_msg = "你连武器都没有，被领主一掌拍出了大殿——所幸逃得快。"
        gaps = equipment_gap_report(world.STATE) or "全部装备"
        world.STATE.boss_fights_lost += 1
        logger.info(
            "[tool] challenge_boss -> 资格不足强闯，装备清零（第 {} 次败退）",
            world.STATE.boss_fights_lost,
        )
        return _reply(
            f"💀 {reset_msg}\n"
            f"（装备总等级 {total_levels(world.STATE)}/{len(EQUIP_SLOTS) * FORGE_MAX_LEVEL}，"
            f"未达成『全部 6 件 {FORGE_MAX_LEVEL} 级』）\n"
            f"缺口报告：{gaps}。\n"
            f"经验保住了（当前 {world.STATE.xp} 点），但装备要重新锻造。"
            f"攒够经验、把 6 件全部锻到 {FORGE_MAX_LEVEL} 级，再来复仇！"
        )

    # 门槛达成：回合制结算，勇者必胜
    rounds = -(-BOSS_HP // world.STATE.attack)  # 向上取整需要的回合数
    world.STATE.boss_hp = 0
    logger.info("[tool] challenge_boss -> 胜利（{} 回合）", rounds)
    return _reply(
        f"⚔️ 最终决战！你的攻击力 {world.STATE.attack}，"
        f"经过 {rounds} 个回合的鏖战，地牢之主轰然倒地！\n"
        "===== 通关结算 =====\n"
        f"最终 HP：{world.STATE.hp}    总等级：{total_levels(world.STATE)}/"
        f"{len(EQUIP_SLOTS) * FORGE_MAX_LEVEL}    剩余经验：{world.STATE.xp}\n"
        "暗影地牢恢复了平静。恭喜你，AI 勇者「阿爪」！"
    )


# ---------------------------------------------------------------------------
# 9. 篝火休息
# ---------------------------------------------------------------------------


def rest_at_bonfire() -> ToolResponse:
    """在篝火旁休息：消耗 5 经验，回复 10 点 HP（每局最多 3 次）。

    Returns:
        `ToolResponse`:
            HP 变化与剩余次数；经验不足或次数用尽时拒绝。
    """
    if world.STATE.rest_used >= REST_MAX:
        return _error(f"篝火今天已经休息过 {REST_MAX} 次，不能再休了。")
    if world.STATE.xp < REST_COST:
        return _error(
            f"休息需要 {REST_COST} 经验，当前只有 {world.STATE.xp} 点。先去打怪。"
        )
    world.STATE.xp -= REST_COST
    world.STATE.rest_used += 1
    world.STATE.hp += REST_HEAL
    logger.info("[tool] rest_at_bonfire")
    return _reply(
        f"你在篝火旁歇了一会儿：HP +{REST_HEAL} → {world.STATE.hp}，"
        f"经验 −{REST_COST} → {world.STATE.xp}。剩余次数：{REST_MAX - world.STATE.rest_used}。"
    )


def reset_world() -> None:
    """重置世界（新开一局用）。"""
    global STATE
    STATE = GameState()


__all__ = [
    "STATE",
    "GameState",
    "challenge_boss",
    "create_map",
    "create_weapon",
    "fight_monsters",
    "forge_equipment",
    "query_status",
    "reset_world",
    "rest_at_bonfire",
    "search_treasure",
    "spawn_monsters",
]
