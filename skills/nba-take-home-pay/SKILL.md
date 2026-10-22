---
name: nba-take-home-pay
description: 查询固定2026–27赛季NBA球员税后合同收入；支持中文姓名、年龄筛选、排名、多人比较、DARKO合理薪资、逐项税额和可保存图片的交互图表。根据Spotrac及本地快照给出情景估算，不代表真实税单，不自动覆盖后续赛季。
license: MIT for project-authored code and documentation; see LICENSE and THIRD_PARTY.md.
metadata:
  season: "2026-27"
---

# 2026–27赛季 NBA 税后薪水

## Hard Rules（核心规则）

1. 先给赛季、对象和“约”的金额，再给表格与图（税后估算、税前薪水、合理薪资）；税务口径、来源日期及不确定因素放在底部。
2. 仅覆盖2026–27；其他赛季不套用本季缓存。“下赛季”按提问日期判断，不符本季时说明范围；快照不得称实时数据。
3. 税后金额采用完整Spotrac薪水减估算税款，不扣联盟托管金、不估算联盟结算；Single不证明单身，婚姻未知需给MFJ对照。
4. 表图使用同次查询；逐人标现役/非现役·保留付款及免税州；当前完整合同与未来续约分列，不用剩余年数冒充签约年数。
5. 查不到不等于人不存在；不猜替代、不填零、不静默漏人；错误按下方回退，不编造数字、图片或来源。

## 快答流程

需要 Python 3.9+、技能目录读取权及脚本执行能力。命令相对技能目录；其他目录用脚本绝对路径。Windows 可把 `python3` 换为 `py -3`。薪资与税后数据随包提供；合理薪资优先用本机缓存，首次缺失时限时读取DARKO公开页面，失败不影响税后查询。普通查询不读全部参考资料、不重算全联盟。

```sh
python3 -X utf8 scripts/take_home.py '杨瀚森' --season 2026-27 --brief --json --chart /absolute/writable/output/nba-pay.html
```

- 首句使用 `rounded_net_usd`，例如“某球员2026–27赛季税后约××万美元”。用户问算式时可直接展开。
- 读取 `visualization.table_markdown` 所指文件作表格，在浏览器/可视化预览中渲染 `visualization.html`，禁止用源码编辑器打开HTML或向用户输出代码/JSON；源数据为 `visualization.data_json`。用户不需要图时不加 `--chart`。
- 每行使用 `roster_status_label`、`roster_team_display`、`team_tax_context`；“非现役”不等于已退役，免税州不证明真实居民地。
- 底部给申报情景、Spotrac快照日期、未计联盟托管及结算的范围说明，以及居民地、配偶收入、伤病/下放、工作日、海外/跨税年、结算、奖金与经纪费等不确定因素。
- 图表固定用随包模板；页首只留查询主题主标题，不展示金色说明副标题和右侧日期块，日期放底部；手机先生成图片供长按保存，支持时提供系统分享。分享或下载成功不等于已入相册。详情见 [回答与图片规范](references/response-guide.md)。

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

## 合理薪资

展示名固定为“合理薪资”，使用独立字段 `fair_salary`，与税前、税后并列；不参与扣税、不算实际合同收入。文字表格、图表金额切换、PNG和视频首幕均保留该项。名次使用 `league_ranks` 的税前/税后联盟名次与 `fair_salary.global_rank` 的DARKO全库名次，禁止把查询名单内顺序当联盟名次；金额切换只重排当前名单。底部小字注明DARKO Fair Salary、比赛截止日期与原生计价口径；不得把抓取日期说成比赛更新日期。缺值写“暂无估值”，保留负值。

`--sort fair --top 10` 查询已匹配估值者排名；结果仅覆盖薪资缓存和DARKO交集，不能声称DARKO全库排名。`python3 scripts/fair_salary.py --refresh` 显式刷新本机缓存。完整估值缓存不随发行包分发。详见[合理薪资口径](references/fair-salary.md)。

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

两人 `--compare` 自动返回 `salary_breakdown`，用第一人减第二人的逐项贡献解释差距；这不是换队因果推断。用户要工资去向图、16:9横屏素材或口播时，在查询中加 `--story --chart /可写目录/比较.html`（1至3人）。1至3人比较附图时自动附带素材包。查询自动导出16:9完整分幕无配音MP4（每幕6秒、0.4秒淡化，保留逐项税款和抵免）；口播稿不是配音，不能声称已生成有声视频。读取 `story_pack.report` 给出表格与约30秒口播，在浏览器渲染 `story_pack.studio`；默认只生成1920×1080横屏PNG与16:9视频，手机长按保存。先给金额，口径放底部；素材来源与假设不得裁掉。

## 按需参考

- 复杂筛选、别名与批量参数：[查询指南](references/query-guide.md)。
- 婚姻默认情景、完整合同、图片与宿主展示：[回答规范](references/response-guide.md)。
- `--explain` 逐税项、`--ledger` 工作日、`--scenario` 自定义和缓存维护：[计算指南](references/calculation-guide.md)。
- 公式与税务证据：[methodology](references/methodology.md)、[tax-sources](references/tax-sources.md)、[CBA特殊情形](references/cba-and-special-cases.md)。

跨季升级必须同时更新薪资、赛程、税年规则、申报情景和计算缓存并校验；`metadata.season`只声明适用范围，不意味着引擎已支持任意赛季。数据日期和覆盖以返回结果及 `--coverage` 为准。

视频由查询入口自动完成：1至3人 `--compare --chart` 或 `--story --chart` 会依次导出分幕、编码MP4、解码验证固定30fps、验证视频及素材哈希、挂回同一结果页。依赖 Node.js、Playwright Chromium、FFmpeg（也支持 imageio-ffmpeg）；可用 NBA_VIDEO_NODE、NBA_VIDEO_FFMPEG 指定可执行文件，NODE_PATH 指定Playwright模块目录。日志走stderr，JSON仍保持可解析。

交付时检查 `video_delivery.status`：只有 `complete` 才可说视频完成，并展示 `story_pack.video.path` 的实际MP4。`failed` 返回退出码3，同时保留文字表格和图表，明确说明失败阶段和缺少的依赖；不得把素材页或口播稿称作视频。依赖修复后用 `python3 scripts/video_pipeline.py /输出/查询.json` 一键补齐，无需重算工资。

## 排名变化与选秀届

`--rank-disruption --top N` 在完整筛选名单内分别算税前/税后排名，再取上升与下降各最多N人；默认各10人。零变化不入榜，正数代表税后排名上升，不是换队因果分析。`--draft-year YYYY` 可组合年龄、球队及排名变化；当前选秀映射只有91人，未独立全量复核，必须说明结果是已收录子集，不能称完整某届名单。图表应显示税前排名、税后排名和升降；计算范围以rank_population为准。

