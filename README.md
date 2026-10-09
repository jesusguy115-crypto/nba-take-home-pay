# NBA Take-Home Pay · 2026–27

查询 NBA 球员税后合同收入。先给估算金额，再说明假设；需要时可展开逐项税额、客场工作日和抵免计算。

**完整公开版随包提供数据和预计算结果，安装后即可离线查询。** 快照截至 2026-10-09，覆盖 520 名球员及其他薪资接收者、1,023 个申报情景和 1,200 场已定常规赛。原创代码及说明采用 MIT，来源与许可范围见 [第三方说明](THIRD_PARTY.md)。

[直接交给 Agent 的安装链接](https://github.com/jesusguy115-crypto/nba-take-home-pay/tree/main/skills/nba-take-home-pay) · [GitHub 仓库](https://github.com/jesusguy115-crypto/nba-take-home-pay) · [下载完整 ZIP](https://github.com/jesusguy115-crypto/nba-take-home-pay/archive/refs/heads/main.zip)

**v0.7.0** 新增固定风格动态薪水账本：深石墨底色、暖白文字、金色横条，内嵌中英文字体；图表、表格和源 JSON 一次生成。可切换金额口径、排序和球员详情，支持手机、离线打开及减少动画设置。图内切换仅重排本次名单。新增 `--order asc` 可直接查询最低薪水。

v0.6.1 在每行明确显示“现役”或“非现役·保留付款”；非现役记录的球队显示为“付款球队”。分类依薪资快照，不将非现役等同于已退役。联盟排名继续包含全部现金接收者，只看现役可指定 `--scope active`。

v0.6.0 加入全员出生日期与年龄筛选，可直接查询“30岁以内税后前十”“未满25岁税后前十”或“25至30岁的森林狼球员”。年龄按查询日计算，生日自动变化，也可指定日期；筛选与排名直接读取本地缓存。

v0.5.1 为快照中 520 人补齐中英文姓名，并统一 1,482 条别名及绰号索引；“安东尼・戴维斯”“浓眉”“AD”“杰森・塔图姆”“塔图姆”“獭兔”均可直接查询。中点、空格、大小写及英文重音符统一处理；重名保留候选，不擅自猜人。普通税后查询、多人比较与旧税前入口共用索引。

v0.5.0 加入联盟结算调整。默认先给“假设最终工资扣减 5.48%”后的税后估值，并显示本季不扣减的合同基准；5.48% 取自上一季报道，仅作历史参照，**不是已知的 2026–27 结算结果**。暂扣 10% 另列税前现金流；税额按结算情景重算，避免重复扣除。批量查询与情景切换继续使用预计算结果。详见 [托管与结算说明](skills/nba-take-home-pay/references/escrow.md) 和 [更新记录](CHANGELOG.md)。

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

> 库里的托管暂扣多少？假设最终扣减 5.48%，税后会少多少？

> 只看约基奇本季没有联盟结算扣减的税后合同基准。

> 查询新赛季税前薪水前十名的税后收入，标注免税州。

> 按税后收入排前十名。

> 30岁以内球员税后收入前十名，标注年龄。

> 00后球员税后薪水前十名。

> 截至2026年10月10日，未满25岁球员的税后薪水前十。

> 森林狼现役名单每个人税后收入是多少？

> 比较库里、杜兰特和杨瀚森的税后收入。

可先在本发布目录运行命令，核对离线查询是否可用。

macOS / Linux：

```sh
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "库里" --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "杜兰特" --explain
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --top 10 --sort gross --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --top 10 --sort net --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --team MIN --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --compare "库里" "杜兰特" "杨瀚森" --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "库里" --filing-status mfj --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "约基奇" --settlement baseline --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --top 10 --sort net --max-age 30 --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --top 10 --sort net --under-age 25 --age-date 2026-10-10 --brief --json
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py --coverage
```

年龄按周岁计算，默认机器当地日期，也可用 `--age-date YYYY-MM-DD` 固定日期。`--max-age 30` 包含30岁，`--under-age 30` 不包含30岁；`--min-age 25 --max-age 30` 为25至30岁（两端包含）。出生年代用 `--birth-year-min 2000 --birth-year-max 2009` 查询00后。先筛年龄或出生年份再排序截取人数。出生日期单独存储并保留来源，变更年龄日期不更新薪资快照，也不触发税额重算。

`--top` 默认按税前 Cash Total 排名，覆盖所有现金薪资接收者；`--sort net` 改按未取整的税后估值排名。`--team` 默认只查该队 Active Roster；`--scope all` 包含该队付款的其他接收者，展示的仍是此人所有付款球队合计收入。多人 `--compare` 默认保留输入顺序，可加 `--sort gross` 或 `--sort net`。不同申报情景和免税州标签会随每行结果保留。

`--settlement historical` 为默认的 5.48% 历史参照情景；`--settlement baseline` 为本季最终扣减和补发均为零的合同基准。两者保持相同的上季工资调整假设，以便比较本季影响；基准仍不代表实际工资已全额返还。普通单人和批量查询都保留当前情景与合同基准。

`--brief --json` 提供回答所需的精简结果；不加 `--brief` 可读取完整普通查询字段。普通 `--filing-status` 直接读取对应缓存，`--explain`、`--ledger` 与自定义 `--scenario` 则重算详细模型。若明确指定美国 Single/MFJ，而比较范围包含猛龙的加拿大情景，工具会报不兼容；不会改套美国税表或悄悄排除猛龙。税后排名需要比较整个筛选范围，跨国排名建议保留各球员默认情景。

Windows：

```powershell
py -3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "库里" --brief --json
```

若没有 `py`，使用已指向 Python 3 的 `python -X utf8`。`-X utf8` 统一文件和终端编码，避免中文 JSON 在不同系统代码页下出错。

若仍出现 `UnicodeEncodeError`，检查是否显式设置了非 UTF-8 的 `PYTHONIOENCODING`；清除该设置或改为 `utf-8` 后重试。

预计算缓存让普通查询、批量查询及已缓存的申报情景直接读结果；实际回复速度还取决于 Agent 的调度和生成速度。

## 数据版本与更新记录

薪资（含上季收入代理）、赛程、球员资料、税则、联盟结算规则和模型代码分组记录内容版本、哈希及可用的来源日期；缓存生成时间单列，不能当成来源更新时间。`--coverage` 可查看版本与按赛程明细计算的覆盖情况，未定比赛数不再写死为每队两场。

若提示数据或模型指纹变化，检查文件完整性，确认更新后运行：

```sh
python3 -X utf8 skills/nba-take-home-pay/scripts/build_estimates.py
```

重建会生成 `assets/update-report-2026-27.json`，记录与前一缓存相比发生变化的输入类别、球员工资/球队/情景字段和各申报情景税后金额差；有变化的报告保存在 `assets/update-history-2026-27.json`。共同变化的输入只说明可能相关的因素，金额差并非各因素的精确因果拆分。首次从旧缓存升级时，旧的分项哈希可能未知，报告会明确说明。

这些文件位于技能目录下。重建不会访问网站或更新原始数据；本版薪资及赛程快照仍为 **2026-10-09**，联盟结算规则核对日为 **2026-10-10**。换入新输入后再重建，来源日期才随输入更新。本仓库 `.gitattributes` 保持文本 LF 换行，避免 Windows Git 自动换行造成指纹不一致。

## 高级用法：更换数据

本包已附完整快照，首次使用无需导入。需要更换或更新数据时，可在发行根目录运行：

```sh
python3 -X utf8 import_data.py --source "已有数据的 assets 文件夹"
```

也可对已安装的技能根目录中的 `import_data.py` 运行同一命令。工具只接收本项目定义的 JSON 格式；已有文件时默认拒绝替换，确认更新可加 `--force`，成功替换后保留旧数据备份，并以目标原有缓存为基准生成变化报告、延续更新历史。详见 [输入格式与验证](DATA_FORMAT.md)。这一步不会抓取来源网站。

## 能覆盖哪些 Agent

符合 [Agent Skills 规范](https://agentskills.io/specification)、能读取附带数据并运行 Python 的宿主，可按其安装方式使用。无原生 Skill 支持但有文件和执行能力的 Agent，也可显式读取 `SKILL.md` 后运行脚本；这不等于原生自动发现。

只有聊天功能、无法安装文件或执行脚本的产品，无法直接运行本包。如需覆盖支持 MCP/API 的其他客户端，可后续增加服务接口；当前包没有托管服务或 MCP 服务。

## 计算方法

见技能内的 [计算方法](skills/nba-take-home-pay/references/methodology.md)、[托管与结算](skills/nba-take-home-pay/references/escrow.md)、[数据覆盖](skills/nba-take-home-pay/references/2026-27-data.md)、[婚姻与申报身份政策](skills/nba-take-home-pay/references/player-profile-policy.md)。主结果已纳入明确假设的最终工资调整；暂扣只列税前现金流，不声称银行实收。返还及补发的实际付款税年未知，默认按原 24 期工资比例归属；经纪费、会费和自愿扣款没有默认扣除。

## 表格与交互图表

在技能目录运行，输出路径可按需修改：

```sh
python3 -X utf8 scripts/take_home.py --min-age 35 --top 10 --sort net --order asc --age-date 2026-10-10 --brief --json --chart ./35-plus-lowest.html
python3 -X utf8 scripts/take_home.py '库里' --brief --json --chart ./curry.html
```

命令同时生成 `.html`、`.md` 与 `.json`，用浏览器打开 HTML 即可交互，不需要服务器或网络。字体和脚本均内嵌。其他 Agent 若不能在聊天中内嵌 HTML，可提供文件下载；仅安装 Skill 不会增加宿主的 HTML 展示能力。

[固定样式说明](skills/nba-take-home-pay/references/chart-design.md) · [示例 HTML](examples/35-plus-lowest.html) · [示例表格](examples/35-plus-lowest.md)。GitHub 文件页展示源码，下载 HTML 后用浏览器打开即可操作。
