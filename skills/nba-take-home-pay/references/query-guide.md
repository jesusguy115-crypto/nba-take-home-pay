# 查询参数与筛选

## 姓名匹配

直接把用户给出的中文或英文姓名传给脚本，无需先尝试英文全名。`assets/player-name-index-2026-27.json` 按球员 ID 统一收录中英文全名、常用译名和绰号；税后单查、多人比较与旧税前查询共用解析器。中点（`·`、`・`）、空格、大小写及英文重音符会统一处理。全名优先，不用模糊子串把不存在的姓名猜成另一人。

例如“安东尼・戴维斯”“浓眉”“AD”指向同一人；“杰森・塔图姆”“塔图姆”“獭兔”指向同一人。“格林”“鲍尔”等歧义名应按返回候选请求补充球队或全名；只有球队能唯一确定候选时才自动选择。索引中记录姓名来源和校核状态，不把姓名来源用于覆盖 Spotrac 的薪资或球队数据。`--coverage` 可查看姓名覆盖。

## 批量查询：一次读缓存

识别用户的排名口径，直接运行一次批量命令，不逐人启动脚本或联网。命令相对于技能目录：

```sh
# 税前薪水前十人的税后收入（默认所有现金薪资接收者）
python3 -X utf8 scripts/take_home.py --top 10 --sort gross --brief --json
# 税后估值前十
python3 -X utf8 scripts/take_home.py --top 10 --sort net --brief --json
# 森林狼 Active Roster 名单
python3 -X utf8 scripts/take_home.py --team MIN --brief --json
# 森林狼全部付款接收者，包括非 Active Roster
python3 -X utf8 scripts/take_home.py --team MIN --scope all --brief --json
# 按输入顺序比较多人
python3 -X utf8 scripts/take_home.py --compare '库里' '杜兰特' '杨瀚森' --brief --json
```

`--top` 默认 `--sort gross`；“薪水前十的税后收入”通常采用这个口径。“税后收入最高”使用 `--sort net`，排名依据未取整的税后估值，不依据展示取整值。多人比较可显式加 `--sort gross` 或 `--sort net`；球队筛选可与 `--top` 组合。`--scope active` 仅含 Active Roster，`--scope all` 含其他现金薪资接收者；按球队查询默认 active，联盟排名默认 all。

身份标注、申报情景及底部说明遵循 SKILL.md 核心规则和 [回答规范](response-guide.md)。球队 `--scope all` 是付款关联筛选，金额为同一球员跨队付款合计，不能说成该队单独支付。

`--brief --json` 为普通回答保留所需字段；用户要求完整普通记录时去掉 `--brief`。`--filing-status single` 或 `mfj` 可用于已有美国情景的快查，直接读缓存；猛龙采用 `individual_canada`。自定义情景、逐税项解释和工作日账仍通过计算引擎生成。不能为追求快答混用金额与另一申报身份的标签。

批量明确指定美国 Single/MFJ 时，只能用于支持该情景的球员。税前前N名先确定名单再选择情景；税后排名须先计算整个筛选范围的比较值，范围含猛龙时不能统一套Single/MFJ。遇到不兼容返回，说明原因并保留默认跨国情景或按用户指定的美国球队/姓名范围比较，不擅自排除猛龙。默认批量查询可混合美国与加拿大情景，但必须标明每行情景。

## 年龄与年龄范围排名

出生日期已保存在 `assets/player-birthdates-2026-27.json`，当前覆盖520人。普通单查、比较和排名均返回周岁 `age`、生日、年龄基准日 `age_as_of` 及来源。年龄按查询当天计算，默认读取运行机器当地日期；用户语境日期或时区不同、明确指定某天时，传入 `--age-date YYYY-MM-DD` 并在回答标明该日。生日当天增长一岁；2月29日出生者在非闰年按3月1日增长。

“30岁以内／不超过30岁”使用 `--max-age 30`（含30）。“未满30岁／小于30岁／under 30”使用 `--under-age 30`（不含30）。“30岁及以上”使用 `--min-age 30`；“超过30岁”使用 `--min-age 31`。“25至30岁”同时使用 `--min-age 25 --max-age 30`。不要把“税后前十”误用税前排序。

```sh
# 30岁以内，按实际未取整税后估值降序，先筛年龄再取前十
python3 -X utf8 scripts/take_home.py --top 10 --sort net --max-age 30 --brief --json
# 未满25岁，年龄按指定日期
python3 -X utf8 scripts/take_home.py --top 10 --sort net --under-age 25 --age-date 2026-10-10 --brief --json
# 森林狼25至30岁球员
python3 -X utf8 scripts/take_home.py --team MIN --min-age 25 --max-age 30 --sort net --brief --json
```

“00后”使用 `--birth-year-min 2000 --birth-year-max 2009`，结合 `--top 10 --sort net --brief --json`；“90后”同理设1990至1999。按出生年份筛选，不能用当前年龄上限代替出生年代。

年龄范围可与球队、现役/全部付款范围、结算情景及申报情景组合；从本地出生日期和税后缓存直接筛选，不联网、不重算税额。结果表增加年龄列，标明年龄基准日及边界是否含该年龄。年龄基准日不改变2026–27薪资、球队及税则快照；不能把指定日期下的年龄排名说成该日的实时工资排名。遇到筛选范围中出生日期缺失，脚本会报错并列人名，不能偷偷排除后宣称完整Top10。

## 免税州标注

单人回答和多人排名都必须读取`team_tax_context`：若`team_in_no_state_income_tax_state`为true，在球队旁明确写州名及“免税州”，例如“热火｜佛罗里达州（免税州）”。NBA对应球队为得克萨斯州的火箭/独行侠/马刺、佛罗里达州的热火/魔术、田纳西州的灰熊。多人表格可在“球队/州”列合并显示，不省略标注。

这里“免税州”专指无州个人所得税；联邦税、雇员工资税及适用的客场州/地方税仍计入。标签描述球队所在地，不证明球员真实税籍。用户将居民地覆盖为另一州时，另说明实际采用的居民州情景，不能因为球队在免税州就免掉该居民州税。

