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
```

## 依赖

```bash
pip install pyyaml python-dotenv openai
```

## 许可证

MIT
