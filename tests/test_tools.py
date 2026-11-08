"""游戏规则的单元测试：不联网，纯本地验证世界状态的执法逻辑。"""

from __future__ import annotations

import pytest

from shadow_dungeon import config
from shadow_dungeon.game import tools
from shadow_dungeon.game import state as world
from shadow_dungeon.game.state import GameState, reset_equipment, reset_world


@pytest.fixture(autouse=True)
def fresh_world():
    """每个用例都拿一个干净的世界。"""
    reset_world()
    yield
    reset_world()


# ---------------------------------------------------------------------------
# 基础流程
# ---------------------------------------------------------------------------


def test_spawn_requires_map():
    res = tools.spawn_monsters(5)
    assert "Error" in res.content[0]["text"]


def test_spawn_limit_rejected():
    tools.create_map("腐朽回廊", "普通")
    res = tools.spawn_monsters(config.SPAWN_LIMIT + 1)
    assert "Error" in res.content[0]["text"]
    assert world.STATE.monsters_alive == 0


def test_fight_gains_xp_and_takes_damage():
    tools.create_map("腐朽回廊", "普通")
    tools.spawn_monsters(25)
    res = tools.fight_monsters("all")
    text = res.content[0]["text"]
    assert world.STATE.xp == 25
    assert world.STATE.hp == config.HERO_START_HP - 25  # 裸装痛期
    assert "裸装痛期" in text


def test_armor_grants_safe_period():
    tools.create_map("腐朽回廊", "普通")
    tools.spawn_monsters(25)
    tools.fight_monsters("all")           # 裸装：掉 25 血
    world.STATE.xp += 100                 # 作弊式补经验，专注测护甲
    tools.forge_equipment("胸甲")          # 护甲 3 ≥ 1 → 安全期
    tools.spawn_monsters(25)
    tools.fight_monsters("all")
    assert world.STATE.hp == config.HERO_START_HP - 25  # 零损伤


def test_weapon_cannot_be_forged_before_claiming():
    tools.create_map("腐朽回廊", "普通")
    world.STATE.xp = 100
    res = tools.forge_equipment("武器")
    assert "Error" in res.content[0]["text"]
    assert "create_weapon" in res.content[0]["text"]


# ---------------------------------------------------------------------------
# 领主战：资格不足 → 装备清零 + 逃跑（v2 核心玩法）
# ---------------------------------------------------------------------------


def test_boss_defeat_resets_equipment_and_hero_escapes():
    tools.create_map("腐朽回廊", "普通")
    tools.create_weapon("木剑", "橡木")
    world.STATE.xp = 200
    for _ in range(5):                    # 只锻 5 级，远不到全满
        tools.forge_equipment("胸甲")
    assert world.STATE.equipment.get("胸甲") == 5

    res = tools.challenge_boss()
    text = res.content[0]["text"]
    assert "打回了 0 级" in text           # 领主之怒：装备清零
    assert "逃" in text                   # 勇者不阵亡，逃跑保命
    assert world.STATE.equipment == {}    # 装备全没
    assert world.STATE.has_weapon is False
    assert world.STATE.attack == config.HERO_START_ATTACK
    assert world.STATE.xp == 200 - 50  # 锻造花掉的 50 扣掉了，但经验不清零
    assert world.STATE.boss_fights_lost == 1
    assert world.STATE.boss_hp == config.BOSS_HP  # 领主没掉血


def test_boss_immune_message_when_naked():
    tools.create_map("腐朽回廊", "普通")
    res = tools.challenge_boss()
    text = res.content[0]["text"]
    assert "逃" in text
    assert "缺口报告" in text             # 缺口报告：逐件列出差距
    assert "未达成" in text


def test_boss_victory_requires_all_maxed():
    tools.create_map("腐朽回廊", "普通")
    tools.create_weapon("木剑", "橡木")
    world.STATE.xp = 10_000
    for slot in config.EQUIP_SLOTS:       # 全部满级
        for _ in range(config.FORGE_MAX_LEVEL):
            tools.forge_equipment(slot)
    res = tools.challenge_boss()
    text = res.content[0]["text"]
    assert "轰然倒地" in text
    assert world.STATE.boss_hp == 0


def test_boss_repeat_challenge_is_idempotent():
    tools.create_map("腐朽回廊", "普通")
    world.STATE.boss_hp = 0
    res = tools.challenge_boss()
    assert "已通关" in res.content[0]["text"]


# ---------------------------------------------------------------------------
# 经济与次数执法
# ---------------------------------------------------------------------------


def test_forge_rejects_when_xp_insufficient():
    tools.create_map("腐朽回廊", "普通")
    res = tools.forge_equipment("胸甲")
    assert "经验不足" in res.content[0]["text"]


def test_forge_max_level_cap():
    tools.create_map("腐朽回廊", "普通")
    world.STATE.xp = 10_000
    for _ in range(config.FORGE_MAX_LEVEL):
        tools.forge_equipment("胸甲")
    res = tools.forge_equipment("胸甲")
    assert "满级" in res.content[0]["text"]


def test_rest_limits_and_cost():
    tools.create_map("腐朽回廊", "普通")
    world.STATE.xp = 100
    world.STATE.hp = 10
    for _ in range(config.REST_MAX):
        tools.rest_at_bonfire()
    res = tools.rest_at_bonfire()
    assert "不能再休" in res.content[0]["text"]


def test_treasure_is_one_shot():
    tools.create_map("腐朽回廊", "普通")
    tools.search_treasure()
    res = tools.search_treasure()
    assert "已经被你搜刮" in res.content[0]["text"]


def test_reset_equipment_helper():
    state = GameState()
    state.equipment = {"胸甲": 9, "武器": 10}
    state.has_weapon = True
    state.attack = 18
    reset_equipment(state)
    assert state.equipment == {}
    assert state.has_weapon is False
    assert state.attack == config.HERO_START_ATTACK
