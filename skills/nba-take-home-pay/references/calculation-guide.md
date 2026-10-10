# 计算解释与数据维护

## 联盟结算：保留金额与暂扣分开

默认 `--settlement historical` 为历史参照情景，本季最终扣减5.48%；`--settlement baseline` 为本季最终扣减及补发均为零的合同基准。两者均为缓存快查，可与 `--filing-status` 和批量选项组合。按税后排名时使用当前所选结算情景，不混用另一情景的排序。

读取 `escrow_scenario`、`contract_baseline`、`settlement_impact` 和 `cashflow_scenario`，保留脚本的结算标签及税年限制。暂扣比例默认10%，只列税前现金流，不声称银行实收；不能在已调整的税后估值上再扣一次暂扣额。最终扣减应先改变工资税基，再重算税额；经纪费另列。历史参照不等于统计预测或误差区间。

`--scenario` 支持 `final_reduction_rate`、`withholding_rate`、`prior_season_final_reduction_rate` 及 `settlement_bonus_usd`。指定金额为已知事实时保留证据，否则标为假设。解释条款、返还、补发及税年归属时读取 [托管与结算](escrow.md)，不要沿用旧版“托管只是暂扣、不会影响最终收入”的说法。

## 计算过程与来源

用户问“怎么算的”“逐笔税”“为什么这个数”时，运行 `python3 -X utf8 scripts/take_home.py '姓名' --explain`。这是完整结构化计算记录，不必读源代码重算。先列合同薪资、最终扣减/补发、结算后工资及与合同基准的税额差，再按两税年展示：调整后的年度工资代理、税档/扣除、归属本赛季的比例、居民州税、每个客场税区收入与税、各方向抵免、地方税、工资税和境外净税。逐档金额在 `years[].national_detail` 与各州 `detail` 中；按字段列出实际算式及来源。

非居民税档是否已分摊须看返回的`allocation_method/allocation_status`及字段名。东部多数税区的逐档行已分摊，西部有些保留全收入税档供参考；不要再次乘比例，也不要把参考税档当来源税额。MA/CA附加税及OR来源累进税按各自规则处理。`years[].components` 为年度模型，`season_attributed_components` 才是赛季归属；境外税单独按履职税年计入赛季明细。

`--ledger` 返回逐日假设账，明确区分已公布比赛场地、推定行程和用户覆盖。比赛表不能证明球员实际出席。

深入解释时按需读取：

- [计算口径、公式与情景输入](methodology.md)
- [托管暂扣、最终结算与税年假设](escrow.md)
- [NBA劳资协议：杯赛、伤病、下放与季后赛](cba-and-special-cases.md)
- [税务来源索引](tax-sources.md)；详细规则：[西部](tax-west-notes.md)、[东部](tax-east-notes.md)、[联邦与跨境](tax-federal-crossborder-notes.md)
- [薪资与赛程覆盖](2026-27-data.md)

## 数据、维护与边界

缓存截至2026-10-09：Spotrac 30队、533笔现金记录、520名接收者（504名Active Roster）；税后缓存覆盖全部520人，美国球队球员同时缓存Single与MFJ工资情景；猛龙保留加拿大个人申报情景。该快照中NBA官方已定常规赛1200场；查询时以返回的 `schedule_coverage` 或 `--coverage` 的动态统计为准，不把旧快照的每队未定场次复制到新数据回答。付款球队、所属队与薪资均按来源快照，不预测未来交易或裁员。

薪资唯一来源为Spotrac对应赛季现金表，使用汇总 `cash_total_usd`；不以cap hit、合同总额或别的网站工资替代。2025–26历史薪资仅帮助构造2026年度工资代理。保留旧 `query_cache.py --season 2026-27 --team MIN --games` 用于税前数据和赛程；它不提供税后结论。

查询脚本仅用Python 3标准库，无API密钥和网络依赖。预计算在 `assets/net-estimates-2026-27.json`；输入/计算代码指纹变化后会要求运行 `python3 -X utf8 scripts/build_estimates.py` 重建。缓存的 `data_versions` 分开保存薪资、赛程、资料、税则、联盟结算规则与代码的内容版本及日期；缓存生成时间不代表来源重新采集。重建同时写入 `assets/update-report-2026-27.json` 和有变化的 `assets/update-history-2026-27.json`，比较旧新金额及观察到的字段变化。相关输入的变化不能说成已精确分解出每一项原因。用户要求最新、数据缺失或已知重大输入变化时，再查官方来源并更新快照及来源日期；不要每次快答自动抓全联盟数据，也不要悄悄把旧快照说成实时行情。

本模型给出可复算的**情景点估计**，尚无真实税单回测，不能保证固定误差率或宣传“误差在±5%”。伤病和下放情景可更新工作地点，不按缺席比赛数自动扣工资。默认税后数已按明确披露的联盟最终扣减假设重算，保留本季零调整合同基准；不额外再扣暂扣金额、经纪费、预扣税或雇主缴款。实际返还/补发的税年尚未知，24期归属只是代理。现金流展示单列，避免重复扣减。

