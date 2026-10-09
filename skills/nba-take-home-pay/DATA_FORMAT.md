# 自带数据与离线导入

本完整发行版已附薪资、赛程、球员公开资料和派生税后缓存，首次使用无需导入。本页说明如何替换已有数据。原创代码许可证不替第三方授予其受保护表达的权利，来源与范围见 `THIRD_PARTY.md`。导入器不访问网络，不抓取网站，也不会生成缺失的薪资、赛程或个人资料。

要求 Python 3.9 或以上，无额外依赖。在仓库发行根目录或已安装技能根目录（包含 `SKILL.md`）都可执行下面的命令。前者默认导入 `skills/nba-take-home-pay/assets`，后者默认导入同级 `assets`；直接安装技能后使用技能根目录内附带的 `import_data.py`。

```sh
python3 -X utf8 import_data.py --source /absolute/path/to/your/assets
```

要导入另一个已安装技能，可显式指定目标。

```sh
python3 -X utf8 import_data.py --source /absolute/path/to/your/assets \
  --skill-path /absolute/path/to/skills/nba-take-home-pay
```

目标 `assets` 非空时默认拒绝覆盖。检查路径后使用 `--force` 表示确认替换；验证成功后，原目录会保留为目标技能内的 `assets.backup-时间-随机标识`。备份保留导入前的数据内容。请勿同时对同一目标运行多个导入进程。

```sh
python3 -X utf8 import_data.py --source /absolute/path/to/your/assets --force
```

导入器仅复制下表的文件。源文件的字节内容会保留，多余文件不会导入。历史赛程、coverage 文件等不属于税后主模型必需输入，旧数据查询辅助脚本依赖的其他文件也不会自动补齐。

| 文件 | 用途 | 是否必需 |
| --- | --- | --- |
| `salaries-2026-27.json` | 当前薪资、付款记录与球员标识 | 必需 |
| `salaries-2025-26.json` | 上季工资，供 2026 税年收入代理使用 | 必需 |
| `schedule-2026-27.json` | 已知比赛日期、球队及实际场馆地点 | 必需 |
| `player-tax-profiles-2026-27.json` | 球员公开资料及申报情景选择依据 | 必需 |
| `net-estimates-2026-27.json` | 与当前输入及模型匹配的派生缓存 | 可选 |
| `player-name-index-2026-27.json` | 按球员 ID 维护中英文全名及别名 | 导入可选；完整安装包必需 |

姓名索引与税务缓存分开维护，修改姓名无需重算税额。来源目录有姓名索引时验证并导入；没有时保留目标已有索引，避免更新薪资后中文名丢失。两边都没有索引时仍可用薪资中的英文全名查询，但不能称为完整中文查询安装。

姓名索引顶层为 `schema_version: 1`、`season: "2026-27"` 和 `players` 数组；每项须有唯一字符串 `player_id`、字符串 `english_name`、字符串数组 `aliases`，`chinese_name` 可为字符串或 null。来源、校核状态及未匹配的历史别名作为元数据保存；当前不存在的球员不能通过别名虚构成本季有薪资记录。不同球员共享的别名会保留为多个候选。

## 已有 JSON 格式

四个输入都必须是 UTF-8 JSON 对象。支持现有完整 `assets` 导出；不会转换 CSV、其他网站导出或不同版本的字段命名。额外元数据和来源证据可以保留。金额使用有限的美元数字，不能是格式化字符串、`NaN` 或 `Infinity`。标识均为字符串，球队代码必须被当前 `duty_days.py` 支持。

### 当前薪资

`salaries-2026-27.json` 顶层必需 `season`（`2026-27`）、`captured_date`（ISO 日期）、`currency`（`USD`）、非空 `players` 和非空 `payment_records`。

每个 `players` 对象必需以下字段。

| 字段 | 类型与含义 |
| --- | --- |
| `player_id` | 唯一字符串，现有格式采用 Spotrac ID 命名空间 |
| `player` | 球员姓名字符串 |
| `player_url` | 原始薪资来源地址字符串 |
| `cash_total_usd` | 非负数字，必须等于关联付款记录合计 |
| `paying_teams` | 非空球队代码数组，与关联付款记录球队一致 |
| `payment_record_ids` | 非空、不重复的付款记录 ID 数组 |
| `signing_bonus_usd` | 可选，原格式存在时保留，用于提示签约金的不确定性 |

每个 `payment_records` 对象必需 `record_id`（唯一字符串）、`player_id`（对应球员）、`team`、`source_section`、`cash_total_usd`（非负数字）、`source_url`。`source_section` 的精确值 `Active Roster` 决定当前服务付款；其他分类按模型既有规则处理。不能为了通过导入而把非服务付款改成 Active Roster。

### 历史薪资

`salaries-2025-26.json` 顶层必需 `season`（`2025-26`）、`captured_date`、`currency`（`USD`）和非空 `players`。税后模型从每个历史球员对象读取唯一字符串 `player_id` 及非负数字 `cash_total_usd`。完整旧格式的付款记录和其他字段可保留。个别当前球员没有上季记录时，模型会使用其当前工资作代理并标注不确定性；这不允许整个历史输入文件缺失。

### 赛程

`schedule-2026-27.json` 顶层必需 `season`（`2026-27`）、`source_url` 和非空 `games`。

每场比赛必需 `game_id`（唯一字符串）、`date_et`（ISO 日期）、`home`、`away`、`arena_country`、`arena_state`、`arena_city`。地点字段为字符串，境外场馆的 `arena_state` 可以为空。`arena_country` 使用模型支持的国家代码；不能拿球队所在地替代中立场地或境外实际场馆。导入器要求日期位于当前模型工作日日历 `2026-09-29` 至 `2027-04-11`，同一球队同一天不能重复比赛，并要求被计算球队出现在赛程中。

保留完整原有数据里的未定比赛说明。不要把未定比赛编进 `games`，也不要把赛程当作球员实际出勤。当前模型保留既有赛程窗口；覆盖统计从已定比赛明细和每队82场的常规赛目标推导，不沿用固定未定场次数。导入通过不代表任意新赛程都适用现有税务模型。

### 球员资料

`player-tax-profiles-2026-27.json` 顶层必需 `season`（`2026-27`）与 `profiles` 对象。`profiles` 的键是当前薪资的 `player_id`，每个当前球员都必须有记录。

每份记录必需相同的 `player_id`、`marital_status`、`actual_filing_status` 字符串。模型将 `married` 或 `married_reported` 用于默认 MFJ 工资情景，其他状态走 Single 工资参考情景。请保留既有 `evidence`、`source`、日期、`review_status` 和未知状态说明；公开婚姻证据不能证明真实申报方式。未知资料应明确记录未知，不能通过编造婚姻、住所或配偶收入来填满数据。

### 可选税后缓存

缓存由 `scripts/build_estimates.py` 生成，应保留完整结构。导入器检查 `season`、`model_fingerprint`、`count` 和 `estimates` 的球员覆盖，并调用 `take_home.py` 做缓存查询与实时逐项计算，比较一位实际球员的主要金额。

`model_fingerprint` 是 `estimate.py` 定义的 SHA-256 指纹，覆盖四个必需输入的文件名与原始字节，以及模型列出的 Python/税则文件。JSON 重新排版也会改变指纹。指纹只能检查输入与模型的一致性，不能证明来源真实性、授权范围或每一项原始事实。

新版缓存附 `cache_schema_version`、`data_versions` 和 `schedule_coverage`：分别表示缓存结构版本、分类内容版本与日期、由比赛明细推导的覆盖统计。它们不等于实际税单验证或来源实时更新。直接运行 `build_estimates.py` 时，会与同目录旧缓存比较并生成 `update-report-2026-27.json`；有变化的报告会进入 `update-history-2026-27.json`。这两个维护报告不从来源目录照搬。每次导入在缓存验证通过后，会以目标原有缓存为基准重新生成最新报告，并保留目标原有更新历史；即使传入已有缓存也会记录本次比较。未发生变化的重复导入不会新增历史条目。目标历史格式损坏时会在替换前报错，旧数据保持不变。

已有缓存指纹不匹配会拒绝导入。请在自己的一份源目录副本中移除旧 `net-estimates-2026-27.json`，再重新导入。没有缓存时，导入器会在临时目录运行 `build_estimates.py`，生成缓存后再执行同样的查询验证。

## 验证、替换与使用

验证发生在目标技能旁的临时目录，仅复制目标模型脚本和允许的输入文件。通过结构检查、指纹核对及真实查询，并在临时目录完成更新报告后，导入器才通过同一文件系统上的目录重命名安装 `assets`。替换已有数据时先移至备份，再安装新目录；若安装重命名失败，会尝试恢复原目录。验证失败不会触碰原 `assets`。两次目录重命名之间有很短的不可查询窗口，请在没有并发查询时导入；这不是断电事务保证。

成功返回的 JSON 包含 `update_report`、`update_history` 路径、`player_change_count` 和 `comparison_status`，便于查看本次导入的变化。

成功后，在仓库发行根目录可以执行以下命令。

```sh
python3 -X utf8 skills/nba-take-home-pay/scripts/take_home.py "Stephen Curry" --json
```

如果当前目录是已安装技能根目录，则执行 `python3 -X utf8 scripts/take_home.py "Stephen Curry" --json`。使用导入数据中存在的英文全名或 `player_id`；上例球员是否存在取决于你自己的数据。若指定了 `--skill-path`，相应替换脚本路径。

`build_estimates.py` **只对已有四份输入重新计算，不会获取数据**。缺少完整输入时，模型无法回答球员税后收入；不能用空文件、假金额或编造赛程绕过这个要求。

## 导入测试

测试不附送数据夹具。可以显式提供已有完整输入，测试仅在系统临时目录内复制和修改数据，不改变源目录或发行目录。

```sh
NBA_IMPORT_TEST_SOURCE=/absolute/path/to/your/assets \
  python3 -m unittest discover -s tests -p test_import_data.py -v
```

未设置变量且发行目录未安装完整数据时，相关集成测试会跳过。
