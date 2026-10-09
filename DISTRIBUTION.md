# 完整公开版与数据来源

本发行版通过 [GitHub 仓库](https://github.com/jesusguy115-crypto/nba-take-home-pay) 分发，随包提供计算代码、结构化事实数据和预计算结果。快照日期为 2026-10-09，覆盖 520 名球员及其他薪资接收者、1,023 个申报情景和 1,200 场已定常规赛，可直接离线查询。

| 文件范围 | 来源或性质 |
| --- | --- |
| `assets/salaries-*.json` | 来自 Spotrac 的工资现金金额、球队及相关事实记录，保留来源链接 |
| `assets/schedule-*.json` | 来自 NBA 官方的比赛日期、球队和地点记录 |
| `assets/coverage-*.json` | 数据覆盖统计、校验信息及来源元数据 |
| `assets/net-estimates-*.json` | 本模型生成的情景估算，附薪资、假设和来源字段 |
| `assets/player-tax-profiles-*.json` | 公开报道中的事实归纳和来源索引，不是私人报税资料 |
| `scripts/` 和 `references/` | 本项目计算代码、税则参数、方法解释和来源索引 |

原创代码及说明采用 [MIT](LICENSE)。事实记录、网页表达、数据库权利和网站访问条款分别看待；本项目许可证不替第三方网站授予其文字、编排、商标或其他表达的权利。项目不声称获得 Spotrac 或 NBA 的单独授权或官方背书，详见 [第三方说明](THIRD_PARTY.md)。

发行内容限定为本目录；浏览器记录、账户信息、对话记录和原始网页文件不纳入发行。根目录 `plugin.json` 记录实际发布者及仓库信息；GitHub 发行不表示已在任何厂商插件市场上架。
