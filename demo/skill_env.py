"""生成早期的代码审查演示技能，展示指令、引用文档和脚本三层资源。

当前写作智能体入口没有调用此函数；只有显式调用时才会写入示例文件。
"""

from pathlib import Path


def setup_demo_environment():
    """在当前工作目录下创建 code-reviewer 技能，并返回技能根目录。

    生成 SKILL.md、references/style-guide.md 和 scripts/lint.sh。
    目录已存在时可以复用，但同名文件会被覆盖；此函数用于演示三级加载，
    其中的检查脚本仅打印预设消息，不会真正扫描项目代码。
    """
    home = Path.cwd()
    skills_dir = home / ".claude" / "skills" / "code-reviewer"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # 第二级资源：头部元数据用于选择技能，正文告诉模型接下来如何调用资源。
    skill_md = skills_dir / "SKILL.md"
    skill_md.write_text("""---
name: code-reviewer
description: 在代码提交前进行审查，检查潜在bug、性能问题和风格违规。当用户提到"review"、"审查代码"、"检查PR"或要求评估代码质量时触发。
author: Claude Code Team
version: 1.0
---

## 工作流程
执行代码审查时，严格遵循以下步骤：
1. **查阅规范**：读取 `references/style-guide.md`文件
2. **执行检查**：运行 `bash scripts/lint.sh`脚本
3. 输出审查报告

## 可用资源
- 规范文档：`references/style-guide.md`
- 检查脚本：`scripts/lint.sh`
  """, encoding="utf-8")

    # 第三级资源：规范文档独立存放，只有执行技能需要它时才交给模型。
    refs_dir = skills_dir / "references"
    refs_dir.mkdir(exist_ok=True)
    (refs_dir / "style-guide.md").write_text("""# 编码规范
- 行长度不超过 100 字符
- 函数必须有 docstring
- 变量使用 camelCase
  """, encoding="utf-8")

    # 第三级资源：演示脚本由命令工具执行，下面的字符串是生成文件的实际内容。
    scripts_dir = skills_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    lint_script = scripts_dir / "lint.sh"
    lint_script.write_text("""#!/bin/bash
  echo "ERROR: utils.py:45 - Line too long (120 > 100)"
  echo "WARNING: app.py:23 - Missing docstring"
  """, encoding="utf-8")
    # 在支持这类权限位的平台上赋予脚本执行权限，便于演示时运行。
    lint_script.chmod(0o755)

    # 返回整个技能根目录，调用者可将其交给 SkillRegistry 扫描。
    return home / ".claude" / "skills"
