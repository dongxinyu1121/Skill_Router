# progressive disclosure
## 核心概念

**Skills Progressive Disclosure** - 渐进披露架构的 AI Agent 框架，通过三级加载机制降低大模型上下文 Token 消耗。也能够帮助Agent集中注意力做正确的事。

渐进披露（Progressive Disclosure）将 Skill 信息分为三级按需加载：

| Level | 内容 | 加载时机 | 典型大小 |
|-------|------|----------|----------|
| **Level 1** | Skill 元数据（名称、描述） | 启动时常驻 | ~100 tokens |
| **Level 2** | SKILL.md 完整指令 | 意图匹配时加载 | ~1000+ tokens |
| **Level 3** | 引用文件（规范、脚本等） | 执行时按需读取 | 视文件大小 |

相比全量加载，可节省 **80%+** 的上下文开销。

## 项目结构

```
progressive_disclosure/
├── agent/                    # 完整的写作 Agent 实现
│   ├── engine.py             # 主流程：模型 → 工具 → 最终回答
│   ├── model.py              # 模型请求与响应解析
│   ├── settings.py           # 环境配置读取
│   ├── prompts.py            # 写作提示词与技能路由规则
│   ├── skills.py             # Skill 数据结构、扫描和读取
│   └── tools/                # 工具包与统一注册表
│       ├── skill.py          # 加载 Skill 完整指令
│       ├── read_file.py      # 读取 Skill 引用资源
│       └── bash.py           # 执行系统命令
├── cli/                      # 终端输入和结果显示
├── scripts/                  # 技能路由评测入口
├── tests/                    # 使用假模型的自动测试
├── demo/                     # 示例 Skill 生成器
├── data/                     # 评测数据和历史结果
├── .env.example              # 本地配置模板
├── .gitignore
└── .claude/skills/           # Skill 目录
    ├── outline-expander/
    │   └── skill.md
    ├── transition-writer/
    │   └── skill.md
    └── ...                    # 其他写作 Skill
```

`.claude/skills/` 存放业务技能内容，`agent/skills.py` 存放读取和管理技能的代码，
两者分别属于数据与实现，不是重复目录。

## 核心模块

| 文件 | 职责 |
|------|------|
| `agent/engine.py` | `WritingAgent`：公开 `run()` 和 `route()`，串起完整执行流程 |
| `agent/skills.py` | `SkillRegistry`：扫描 Skill 目录并管理三级披露数据 |
| `agent/tools/` | 三个工具及统一注册表，Skill 触发 Level 2，ReadFile 支持 Level 3 |
| `agent/model.py` | `ModelClient`：封装 OpenAI 兼容接口并统一响应结构 |
| `cli/agent.py` | 终端输入、退出处理、简洁日志与最终结果显示 |


## 启动方式

### 方式一：真实 LLM 交互

要求：
1. 需要配置 API Key。
2. 使用的大模型需要支持OpenAI的tool调用格式。
3. 使用的大模型工具解析的能力要足够强。

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env：OPENAI_API_KEY=xxx, OPENAI_BASE_URL=xxx, OPENAI_MODEL=xxx
# 程序启动时会优先使用 .env 中的值，覆盖当前终端已有的同名环境变量

# 2. 运行
python -m cli.agent
```

默认只显示技能、工具和最终回答。需要查看模型请求及工具参数时使用：

```bash
python -m cli.agent --verbose
```

启动后进入交互式会话，
- 输入 `我写完了开头，但不知道下一段怎么展开` 会匹配 `outline-expander` 等写作 Skill。
- 输入 `quit`/`exit` 退出。

## 创建 Skill

当前 Skill 位于 `.claude/skills/`。`demo/skill_env.py` 提供一个独立的
`code-reviewer` 示例生成器，主程序不会自动运行或覆盖现有 Skill。

## 测试与评测

```bash
# 使用固定响应的假模型测试主流程，不产生模型费用
python -m unittest discover -s tests -v

# 只校验路由评测数据，不调用模型
python scripts/evaluate_skill_routing.py --validate-only

# 真实评测（需要 .env 配置）
python scripts/evaluate_skill_routing.py --limit 10 --sleep 1
```

数据集 `data/skill_routing_eval.json` 共 100 条，每条含三组人工标注：

- `expected_skills`：严格命中的目标技能
- `acceptable_skills`：可接受的替代技能
- `bad_skills`：不应被调用的技能

评测只取模型**第一轮**响应中的技能选择（`WritingAgent.route()`），不执行技能、
也不评续写质量。指标含义：

| 指标 | 含义 |
|------|------|
| `strict_top1_accuracy` | 第一个选择的技能属于严格目标 |
| `strict_top3_accuracy` | 前三个选择中命中严格目标 |
| `acceptable_hit_rate` | 命中严格目标或可接受替代 |
| `bad_skill_call_rate` | 调用了不应调用的技能 |
| `avg_skill_calls` | 平均技能调用数量 |

### 已有结果对比

同一数据集、100 条样本、全部请求成功：

| 指标 | 提示词 v1 | 提示词 v2 |
|------|-----------|-----------|
| `strict_top1_accuracy` | 73% | **90%** |
| `strict_top3_accuracy` | 94% | 90% |
| `acceptable_hit_rate` | 95% | **99%** |
| `bad_skill_call_rate` | 0% | 0% |
| `avg_skill_calls` | 2.65 | **1.00** |

改进提示词后，首个技能就选对的比例从 73% 升到 90%，同时平均调用数从 2.65
降到 1.00——**更准，也更省**。两份原始结果见
`data/skill_routing_eval_results.json` 与 `data/skill_routing_eval_results_prompt_v2.json`。

## 建议的读代码顺序

本项目的调用关系是「入口 → 编排 → 工具 → 数据」。按下面顺序读最省力：

1. `cli/agent.py` — 看清输入输出边界（有效代码约 20 行）
2. `agent/engine.py` — 只读 `run()`，跳过所有 `_` 开头的方法
3. `agent/tools/__init__.py` — 只看 `execute()` 里开放 `ReadFile` 的那几行
4. `agent/skills.py` — 三级技能数据是怎么来的
5. 其余（`model.py` / `prompts.py` / `settings.py`）按需再看

读到 `self._model.generate(...)` 这类调用时，先记下「它返回什么」，继续往下读，
不要当场跳进另一个文件——那正是最容易迷路的地方。

## 已知限制

- `BashTool` 使用 `shell=True` 直接执行模型给出的命令，仅靠 8 条子串黑名单过滤，
  **容易被绕过，不要对着重要仓库运行**。
- 技能解析只读 frontmatter 顶层的 `name` / `description` / `author` / `version`；
  写成嵌套结构（如 `metadata.author`）时该字段读不到。
- 没有流式输出与实时事件，日志在整轮任务结束后一次性显示。
- 对话历史只存在内存中，进程退出即丢失。

## 历史说明

本仓库经历过一次目录重构。**旧版**布局中的 `runtime/`、`toolkit/`、`core/`、
`skill_core/`，以及 `cli/agent_evaluation.py`、`cli/agent_mock.py`、`tests/test.py`
等文件均已**不存在**，其职责现由 `agent/`（运行层）与 `scripts/`（评测脚本）承担。

若在别处（旧文档、编译缓存、他人笔记）看到指向上述旧路径的说明，请以本文档为准。
仓库中残留的 `__pycache__/`、`.DS_Store`、`__MACOSX/` 等已清理；它们本就未被
git 跟踪，`python` 运行时也会自动重建 `__pycache__/`。

## 依赖

```bash
pip install pyyaml python-dotenv openai
```

> `openai` 是延迟导入的：只跑测试或数据校验时，无需安装它。

## 许可证

MIT
