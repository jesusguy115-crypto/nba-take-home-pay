# NBA Take-Home Pay · 2026–27

查询 NBA 球员税后合同收入。先给估算金额，再说明假设；需要时可展开逐项税额、客场工作日和抵免计算。

**完整公开版随包提供数据和预计算结果，安装后即可离线查询。** 快照截至 2026-10-09，覆盖 520 名球员及其他薪资接收者、1,023 个申报情景和 1,200 场已定常规赛。原创代码及说明采用 MIT，来源与许可范围见 [第三方说明](THIRD_PARTY.md)。

[GitHub 仓库](https://github.com/jesusguy115-crypto/nba-take-home-pay) · [下载完整 ZIP](https://github.com/jesusguy115-crypto/nba-take-home-pay/archive/refs/heads/main.zip)

## 内容与运行要求

- 固定 2026–27 赛季，薪资快照截至 2026-10-09；520 名薪资接收者、1,023 个申报情景，包含已定的 1,200 场常规赛。
- Spotrac 为薪资来源，NBA 官方为赛程来源；保留来源链接和计算口径。
- Python 3.9 及以上，只用标准库，无需 pip 安装依赖、API 密钥或查询时联网。
- 需要宿主能读取完整技能目录并运行 Python。安装工具不能自动给宿主增加执行能力。
- 金额是公开资料下的情景估算，不是私人税单或实际银行到账，不承诺固定误差率。

## 一条命令离线安装

解压后，在本目录运行。个人安装任选所用 Agent；无需 Node.js/npm，也不联网：

```sh
python3 -X utf8 install.py --agent codex --global
python3 -X utf8 install.py --agent claude-code --global
python3 -X utf8 install.py --agent cursor --global
python3 -X utf8 install.py --agent github-copilot --global
```

只在指定项目使用时，将 `--global` 换成 `--project "项目路径"`。Windows 用 `py -3 -X utf8` 代替 `python3 -X utf8`。先加 `--dry-run` 可查看安装目标；已有同名技能时默认拒绝覆盖，确认升级可加 `--force`，旧版会保留为备份。

## 下载后手动安装

复制整个 `skills/nba-take-home-pay` 文件夹到下表中的目录。保留 `SKILL.md`、`scripts`、`assets`、`references` 等全部文件，不能只复制 Markdown。

| Agent | 项目目录下的安装位置 | 个人安装位置 |
| --- | --- | --- |
| Codex | `.agents/skills/nba-take-home-pay/` | `~/.agents/skills/nba-take-home-pay/` |
| Claude Code | `.claude/skills/nba-take-home-pay/` | `~/.claude/skills/nba-take-home-pay/` |
| Cursor | `.cursor/skills/nba-take-home-pay/` | `~/.cursor/skills/nba-take-home-pay/` |
| GitHub Copilot in VS Code | `.github/skills/nba-take-home-pay/` | `~/.copilot/skills/nba-take-home-pay/` |

`~` 表示个人主目录，Windows 可以在用户目录下建立相同的隐藏文件夹。已有同名技能时，先备份旧目录再整体替换，避免混合版本。重新开启会话；若宿主尚未发现技能，按其说明重新加载。

官方依据（核对日 2026-10-09）：[Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills)、[Cursor](https://cursor.com/docs/skills)、[VS Code](https://code.visualstudio.com/docs/agent-customization/agent-skills)。这些是文档支持的安装位置，尚未在四个 Agent 客户端逐一实测。

## 从 GitHub 安装

也可使用第三方 [Vercel Skills CLI](https://github.com/vercel-labs/skills) 从仓库安装：

```sh
npx skills add jesusguy115-crypto/nba-take-home-pay --skill nba-take-home-pay
```

该工具需要 Node.js/npm，交互选择目标 Agent；加 `--global` 可装到个人目录。也可用 `--agent codex`、`--agent claude-code`、`--agent cursor` 或 `--agent github-copilot` 指定目标。Python 运行环境仍需具备。手动安装无需 Node.js。

`skills/nba-take-home-pay/` 是通用 Skill；根目录 `plugin.json` 是可选的便携插件入口。它不表示已被任何插件市场审核或上架。不同厂商的插件市场仍可能要求额外元数据、仓库结构和审核步骤，不能把仓库发布等同于全平台商店上架。

## 使用

安装后对 Agent 说：

> 使用 nba-take-home-pay，查询库里 2026–27 赛季税后薪水，先给估算数字。

> 解释杜兰特的每项税、客场工作日分摊和抵免。

> 查询新赛季税前薪水前十名的税后收入，标注免税州。

可先在本发布目录运行命令，核对离线查询是否可用。

macOS / Linux：

```sh
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "库里" --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "杜兰特" --explain
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --coverage
```

Windows：

```powershell
py -3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "库里" --json
```

若没有 `py`，使用已指向 Python 3 的 `python -X utf8`。`-X utf8` 统一文件和终端编码，避免中文 JSON 在不同系统代码页下出错。

若仍出现 `UnicodeEncodeError`，检查是否显式设置了非 UTF-8 的 `PYTHONIOENCODING`；清除该设置或改为 `utf-8` 后重试。

预计算缓存让普通查询直接读结果；实际回复速度还取决于 Agent 的调度和生成速度。若提示数据或模型指纹变化，检查文件完整性，确认更新后运行：

```sh
python3 -X utf8 skills/nba-take-home-pay/scripts/build_estimates.py
```

本仓库 `.gitattributes` 保持文本 LF 换行，避免 Windows Git 自动换行造成指纹不一致。

## 高级用法：更换数据

本包已附完整快照，首次使用无需导入。需要更换或更新数据时，可在发行根目录运行：

```sh
python3 -X utf8 import_data.py --source "已有数据的 assets 文件夹"
```

也可对已安装的技能根目录中的 `import_data.py` 运行同一命令。工具只接收本项目定义的 JSON 格式；已有文件时默认拒绝替换，确认更新可加 `--force`，成功替换后保留旧数据备份。详见 [输入格式与验证](DATA_FORMAT.md)。这一步不会抓取来源网站。

## 能覆盖哪些 Agent

符合 [Agent Skills 规范](https://agentskills.io/specification)、能读取附带数据并运行 Python 的宿主，可按其安装方式使用。无原生 Skill 支持但有文件和执行能力的 Agent，也可显式读取 `SKILL.md` 后运行脚本；这不等于原生自动发现。

只有聊天功能、无法安装文件或执行脚本的产品，无法直接运行本包。如需覆盖支持 MCP/API 的其他客户端，可后续增加服务接口；当前包没有托管服务或 MCP 服务。

## 计算方法

见技能内的 [计算方法](skills/nba-take-home-pay/references/methodology.md)、[数据覆盖](skills/nba-take-home-pay/references/2026-27-data.md)、[婚姻与申报身份政策](skills/nba-take-home-pay/references/player-profile-policy.md)。经纪费、联盟临时托管与税负分别处理，默认数字不额外扣除前两者。
