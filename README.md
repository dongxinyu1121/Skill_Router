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
├── cli/                      # 入口层
├── core/                     # 配置、提示词、LLM 客户端
├── demo/                     # 演示环境
├── skill_core/               # Skill 数据与注册表
├── toolkit/                  # 工具层：Skill / ReadFile / Bash
├── runtime/                  # Agent 运行层：共享基类、loop、mock
├── .env.example              # 本地配置模板
├── .gitignore
└── .claude/skills/           # Skill 目录
    └── code-reviewer/
        ├── SKILL.md
        ├── references/
        │   └── style-guide.md
        └── scripts/
            └── lint.sh
```
项目中skills只是演示示例。你可以尝试其它的skill。

## 核心模块

| 文件 | 职责 |
|------|------|
| `skill_core/` | `SkillRegistry` - 扫描 Skill 目录，管理元数据缓存和三级加载 |
| `toolkit/` | `Tool` 基类；`SkillTool` 触发 Level 2；`ReadFileTool` 支持 Level 3 相对路径解析 |
| `core/llms.py` | `LLMClient` - 封装 OpenAI 兼容 API 调用 |
| `runtime/agent_loop.py` | `AgentLoop` - 主循环，处理用户输入、模型推理、工具调用 |
| `cli/` | 各入口脚本：agent |


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

启动后进入交互式会话，
- 输入 `帮我审查一下刚才提交的代码` 会加载code-reviewer/SKILL.md。
- 输入 `quit`/`exit` 退出。

## 创建 Skill

运行 `cli/agent.py` 会自动创建 `.claude/skills/code-reviewer/SKILL.md` 以及相关资源。

可以通过 `demo/skill_env.py` 文件修改 Skill 的内容。

## 依赖

```bash
pip install pyyaml python-dotenv openai
```

## 许可证

MIT
