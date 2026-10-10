---
name: nba-take-home-pay
description: 查询固定2026–27赛季NBA球员税后合同收入；支持中文姓名、年龄筛选、排名、多人比较、逐项税额和可保存图片的交互图表。根据Spotrac及本地快照给出情景估算，不代表真实税单，不自动覆盖后续赛季。
license: MIT for project-authored code and documentation; see LICENSE and THIRD_PARTY.md.
metadata:
  season: "2026-27"
---

# 2026–27赛季 NBA 税后薪水

## Hard Rules（核心规则）

1. 先给赛季、对象和“约”的金额，再给表格与图；税务口径、来源日期及不确定因素放在底部。
2. 仅覆盖2026–27；其他赛季不套用本季缓存。“下赛季”按提问日期判断，不符本季时说明范围；快照不得称实时数据。
3. 税后金额采用脚本结果；最终结算只是情景，10%暂扣不再重复扣；Single不证明单身，婚姻未知需给MFJ对照。
4. 表图使用同次查询；逐人标现役/非现役·保留付款及免税州；当前完整合同与未来续约分列，不用剩余年数冒充签约年数。
5. 查不到不等于人不存在；不猜替代、不填零、不静默漏人；错误按下方回退，不编造数字、图片或来源。

## 快答流程

需要 Python 3.9+、技能目录读取权及脚本执行能力。命令相对技能目录；其他目录用脚本绝对路径。Windows 可把 `python3` 换为 `py -3`。数据随包提供，普通查询不抓网、不读全部参考资料、不重算全联盟。

```sh
python3 -X utf8 scripts/take_home.py '杨瀚森' --season 2026-27 --brief --json --chart /absolute/writable/output/nba-pay.html
```

- 首句使用 `rounded_net_usd`，例如“某球员2026–27赛季税后约××万美元”。用户问算式时可直接展开。
- 读取 `visualization.table_markdown` 所指文件作表格，在浏览器/可视化预览中渲染 `visualization.html`，禁止用源码编辑器打开HTML或向用户输出代码/JSON；源数据为 `visualization.data_json`。用户不需要图时不加 `--chart`。
- 每行使用 `roster_status_label`、`roster_team_display`、`team_tax_context`；“非现役”不等于已退役，免税州不证明真实居民地。
- 底部给 `escrow_scenario`、`contract_baseline`、申报情景、Spotrac快照日期，以及居民地、配偶收入、伤病/下放、工作日、海外/跨税年、结算、奖金与经纪费等不确定因素。
- 图表固定用随包模板；手机先生成图片供长按保存，支持时提供系统分享。分享或下载成功不等于已入相册。详情见 [回答与图片规范](references/response-guide.md)。

## 常用查询

```sh
# 税前最高10人的税后收入；税后排名改用 --sort net
python3 -X utf8 scripts/take_home.py --top 10 --sort gross --brief --json
# 35岁及以上税后最低10人；年龄默认查询当天
python3 -X utf8 scripts/take_home.py --min-age 35 --top 10 --sort net --order asc --brief --json
# 00后税后前10
python3 -X utf8 scripts/take_home.py --birth-year-min 2000 --birth-year-max 2009 --top 10 --sort net --brief --json
# 球队和多人比较
python3 -X utf8 scripts/take_home.py --team MIN --brief --json
python3 -X utf8 scripts/take_home.py --compare '库里' '杜兰特' '杨瀚森' --brief --json
```

成功查询默认补 `--chart`。先筛选再排名，最低用 `--order asc`；联盟默认包含全部现金付款接收者，球队默认现役，用户只看现役用 `--scope active`。30岁以内含30用 `--max-age 30`，未满30用 `--under-age 30`。不同年龄日期传 `--age-date YYYY-MM-DD`。更多边界、姓名消歧、跨国申报比较见 [查询指南](references/query-guide.md)。

## 异常时回退

| 返回/情况 | 告诉用户与后续动作 |
|---|---|
| `ambiguous` | “这个名字对应多名球员，请确认。”列真实 `candidates`，补球队或全名后查询。 |
| `player_not_cached` | “姓名已识别，但2026–27税后缓存未收录。”显示已识别球员，不报0、不用其他年份代替；核查薪资输入后补数据/重建。 |
| `not_found` | “当前姓名索引未匹配，可能是译名或尚未收录，不能据此判断球员不存在。”请补英文名、球队或链接；没有候选时不伪造候选。 |
| `cache_missing` / `cache_stale` | 输入齐全时运行 `scripts/build_estimates.py` 后重试；它不下载任何数据。 |
| `data_missing` / `data_invalid` | 指明缺失/损坏文件；按随包 `DATA_FORMAT.md`、`import_data.py` 恢复或导入，不能只重建空数据。 |
| `permission_denied` / 无Python或执行能力 | 明确需要 Python 3.9+、文件读取/执行权限；图表另需输出目录写权限。不能编造执行结果。 |
| `unsupported_season` | 明确仅支持2026–27，请选择该季或更新整套赛季数据；禁止只改文件名冒充新季。 |
| `query_errors` / 无筛选结果 | 多人查询列出每项错误，不漏人后输出完整比较；空结果说明没有符合筛选条件的缓存记录。 |
| 图表失败 / 其他报错 | 去掉 `--chart` 重试收入查询，成功则先给表格并说明图表失败；其他错误按实际信息解释，不掩盖成查无此人。 |

## 差距解释与视频素材

两人 `--compare` 自动返回 `salary_breakdown`，用第一人减第二人的逐项贡献解释差距；这不是换队因果推断。用户要工资去向图、16:9横屏素材或口播时，在查询中加 `--story --chart /可写目录/比较.html`（1至3人）。1至3人比较附图时自动附带素材包。素材页可生成16:9完整分幕无配音视频（每幕4秒，保留逐项税款和抵免）（浏览器支持时），口播稿不是配音，不能声称已生成有声视频。读取 `story_pack.report` 给出表格与约30秒口播，在浏览器渲染 `story_pack.studio`；默认只生成1920×1080横屏PNG与16:9视频，手机长按保存。先给金额，口径放底部；素材来源与假设不得裁掉。

## 按需参考

- 复杂筛选、别名与批量参数：[查询指南](references/query-guide.md)。
- 婚姻默认情景、完整合同、图片与宿主展示：[回答规范](references/response-guide.md)。
- `--explain` 逐税项、`--ledger` 工作日、`--scenario` 自定义和缓存维护：[计算指南](references/calculation-guide.md)。
- 公式与税务证据：[methodology](references/methodology.md)、[tax-sources](references/tax-sources.md)、[escrow](references/escrow.md)、[CBA特殊情形](references/cba-and-special-cases.md)。

跨季升级必须同时更新薪资、赛程、税年规则、申报情景和计算缓存并校验；`metadata.season`只声明适用范围，不意味着引擎已支持任意赛季。数据日期和覆盖以返回结果及 `--coverage` 为准。

视频优先离线导出：用 `scripts/export_video_frames.cjs studio.html frames目录` 导出全部分幕PNG（需Playwright），再用 `scripts/encode_video.py frames目录 output.mp4 --ffmpeg 可执行路径` 生成1920×1080、30fps、H.264、0.4秒交叉淡化的MP4。浏览器实时录制仅作备用，可能掉帧；没有编码依赖时明确说明，不宣称已生成流畅视频。
