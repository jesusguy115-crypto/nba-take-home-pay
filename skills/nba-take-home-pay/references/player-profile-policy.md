# 球员公开婚姻资料与税务情景

档案文件为 `assets/player-tax-profiles-2026-27.json`。它按本季 Spotrac 薪资快照的 `player_id` 为全部 520 名工资接收者建立记录。覆盖全部名单不代表逐人完成私人生活调查。资料核验日为 2026-10-09，正面婚姻证据采用选择性核验，缺少可靠证据的记录保持 `unknown`。

## 三种状态必须分开

- `marital_status` 只记录公开证据类别，取值为 `unknown`、`married` 或 `unmarried_reported`。`married` 表示有明确公开婚姻记录，并不等于核实了 2026 年或 2027 年最后一天的婚姻状态。
- `actual_filing_status` 为真实申报身份。本次所有记录均为 `unknown`，没有从婚姻、家庭成员、球队或住址推断 MFJ、MFS、Single 或加拿大税务居民身份，也没有搜索私人税单。
- 计算使用的 `filing_status` 是情景选择。公开已婚者可使用明确标注的 MFJ 工资情景，不能把它写成其实际申报；未知者的 Single/MFJ 比较也只是税表情景。

夫妻分报 MFS 不等于 Single；当前美国模块只提供 Single 与 MFJ，不能将其中任何一项冒充已完成 MFS 计算。加拿大按个人报税，本模块保留现有个人计算，婚姻可能影响的配偶抵免等项目尚未核定，不能给猛龙球员套用美国夫妻合报。

## 证据与日期

优先采用 NBA、球队官方文章、媒体指南、球员简介、官方账号及球员本人明确的公开陈述。报道必须确实指向该球员本人，不能把父母、教练、管理人员或队友的妻子错归给球员。球队或 NBA 承载的外部署名报道保留其来源类别，不伪称球队亲自核实。Giannis Antetokounmpo 的证据为本人向 PEOPLE 确认婚礼的公开直接采访，来源记录说明所读取的是 AOL 转载。

每条 `evidence` 保存 `source`、`source_type`、`source_date`、`event_date`、`as_of`、简短事实摘要以及时间适用范围。`source_date` 无法确定时保留 null；网页本次检索时间不冒充文章更新时间。没有明确婚礼日时，不从照片、URL 路径或相关文章推造精确日期。`event_date` 可以只有年或年月，表示原始证据的精度。`tax_year_end_status` 明确把 2026 和 2027 年末状态保留为 unknown。

公开订婚、有孩子、交往对象、人物年龄、单人照片，以及简介未提及配偶，都不足以推出已婚或未婚。缺少结婚新闻也不等于单身。涉及离婚诉讼、传闻或只有陈旧未婚表述时，不据此认定已经离婚或当前未婚。Kevin Durant 的 2016 年未婚陈述仅存作历史证据，当前 `marital_status` 保留 unknown。

`review_status` 的 `not_researched` 表示未做个人定向核验，`no_public_confirmation` 表示已做定向检索但证据不足，`qualifying_marriage_evidence_recorded` 表示已记录明确婚姻证据。默认 unknown 档案的 `source` 和 `source_date` 为 null，`evidence` 为空数组。不得把这些默认记录描述成“已核实单身”。

## 配偶工资与联邦计算接口

`calculate_us(gross, year=2026, filing_status="single", spouse_wages=0)` 的 `gross` 是包含 `spouse_wages` 在内的家庭全年工资，主收入者工资为 `gross - spouse_wages`。配偶工资不得超过家庭工资；Single 情景禁止非零配偶工资。所有金额必须有限且非负。

零配偶工资是只纳入球员合同工资的建模选择，不代表配偶没有收入。配偶的商业、自雇、投资、代言等收入也不能硬塞入工资参数。本次档案没有核定任何配偶收入。用户提供年度配偶工资时应清楚注明年份、币种、工资性质及其是否已计入家庭合计。

返回值中的 `gross`、`federal`、`payroll`、`tax` 和净额是家庭合计。`payroll_by_person.primary` 和 `.spouse` 各含工资、Social Security 工资税基、Social Security、Medicare、Additional Medicare 及工资税合计。

2026 年 Social Security 员工税率为 6.2%，184,500 美元上限分别用于两人的工资，不能只给家庭使用一次上限。普通 Medicare 为全部工资的 1.45%；Additional Medicare 的 MFJ 家庭门槛为 250,000 美元，Single 为 200,000 美元。家庭 Additional Medicare 按两人工资比例展示到个人明细；这是分摊约定，不是分别计算的法律义务或工资单预扣。2027 继续显式使用 2026 参数代理。

依据为 [SSA 2026 参数](https://www.ssa.gov/cola/factsheets/2026.html)、[IRS FICA 税率与上限](https://www.irs.gov/taxtopics/tc751) 及 [IRS Additional Medicare 问答](https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax)。家庭所得税如何归属于球员合同净额，需要由上层估算器单独声明分摊规则；本模块的家庭合计不可直接伪装为球员个人税单。
