# 暗影地牢 · Shadow Dungeon

> 基于 [agentscope](https://github.com/agentscope-ai/agentscope) `ReActAgent` 的 AI 自主闯关游戏：
> 勇者「阿爪」自主规划、自主召唤怪物、自主打怪攒经验、自主锻造装备、自主挑战领主——直到通关。

## 玩法

AI 勇者被丢进暗影地牢，唯一的指令是"击败地牢之主"。怎么做，它自己想：

- 🗺️ **创建地图** → 召唤怪物的前置条件
- ⚔️ **召唤怪物 + 战斗** → 每杀 1 只 +1 经验（唯一的货币）
- 🔨 **锻造装备** → 10 经验升 1 级，6 件部位（肩甲/胸甲/鞋子/护腿/腰带/武器）每件满级 5 级
- 🎁 **搜寻宝箱** → 每张地图藏一个，随机 +15 经验或回满血
- 🔥 **篝火休息** → −5 经验回 10 HP，每局 3 次
- 👹 **挑战领主** → **只有全部 6 件满级才有资格**；资格不足强闯会被领主把装备全部打回 0 级，勇者逃跑保命（经验保留，从头再锻）

世界状态的规则执法全部在工具函数里用 `if` 拦截——模型骗不过 `if`。

## 快速开始

```shell
# 1. 安装依赖（uv 自动创建虚拟环境）
uv sync

# 2. 配置模型：复制模板后填入你的 API Key
cp .env.example .env                      # 然后编辑 .env 填入 DASHSCOPE_API_KEY
# 或者直接用环境变量：export DASHSCOPE_API_KEY="sk-..."

# 3. 开跑
uv run shadow-dungeon
# 等价：uv run python -m shadow_dungeon
```

跑起来后，日志里 `[tool]` 开头的行就是勇者真实调用工具的实证，`<<< 阿爪` 是它的回合发言。

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `DASHSCOPE_API_KEY` | 模型 API Key（必填） | — |
| `DASHSCOPE_BASE_URL` | OpenAI 兼容端点 | 见 `config.py` |
| `DASHSCOPE_CHAT_MODEL` | 聊天模型名 | `qwen3.7-max` |

只需要这 3 个变量——模板见 `.env.example`（已入库，可直接参考）。

## 项目结构

```
src/shadow_dungeon/
├── config.py            # 全局配置：模型端点 + 游戏数值配平（改难度只动这里）
├── runner.py            # 冒险驱动：续跑循环 + 超时兜底 + 异常重试
├── __main__.py          # 命令行入口（uv run shadow-dungeon）
├── agent/
│   └── assembly.py      # agent 总装：模型/工具箱/规划本/记忆压缩
└── game/
    ├── state.py         # 世界状态：纯数据账本 + 规则判定函数
    └── tools.py         # 9 个游戏工具：每个都是"执法者"
tests/
└── test_tools.py        # 规则单元测试（不联网，纯本地）
```

## 设计要点

- **模型只负责决策，世界只认 `if`**：召唤上限、经济结算、领主门槛全在工具函数里执法，模型说谎无效。
- **续跑循环**：ReAct 循环的退出条件是"回复不含工具调用"，模型偶尔会把工具调用写成纯文本提前收工——只要领主没倒，就把勇者踢回去继续打。
- **记忆压缩**：长局（200+ 轮）的保险；摘要 schema 用自定义 pydantic 模型，把内置的硬字符上限换成软约束，避免中文摘要撑爆校验。
- **领主之怒（v2 核心玩法）**：装备未满级强闯领主 → 装备全部打回 0 级、勇者逃跑保命。失败可恢复，但代价惨重。

## 运行测试

```shell
uv run pytest tests/ -v
```

## License

MIT
