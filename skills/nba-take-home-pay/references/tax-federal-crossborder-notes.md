# 联邦及跨境税估算参数说明

核验日期：2026-10-09。实现见 `tax_federal.py`，参数与来源清单见 `tax-federal-crossborder.json`。全部是明确假设下的年度工资计算，不能声称知道个人的申报身份、申报记录或银行卡到账。

## 实现接口与货币

- `calculate_us(gross, year=2026, filing_status="single")`：美国居民单身工资情景；可选 `mfj`，配偶收入假设为零。返回联邦税、逐档明细、标准扣除、Social Security、Medicare、Additional Medicare。
- `calculate_canada(gross_usd, year=2026, fx=1.4240)`：加拿大安大略居民单身工资情景；返回加拿大联邦、省税、CPP、EI、抵免及附加税明细。
- `calculate_overseas(country, allocated_usd, year=2026, ...)`：US 球队短期境外履职的最终所得税情景，支持 CA、GB、FR、MX。调用者必须提供工作地点分摊后的报酬。
- `us_foreign_tax_credit(...)`：美国当前年度一般收入类别的外国所得税抵免简化计算。
- `canada_foreign_tax_credit(...)`：按国家先计算加拿大联邦抵免，再计算安大略剩余抵免。美国州和地方所得税须按美国这个国家合并。

所有顶层金额均为美元；带 `_cad`、`_gbp`、`_eur` 的字段使用对应本币。汇率为加拿大央行 2026-10-08 日值，1 USD = 1.4240 CAD、1 GBP = 1.8822 CAD、1 EUR = 1.5950 CAD；这些是估算时固定的快照，不是尚未知晓的税年平均汇率。[加拿大央行](https://www.bankofcanada.ca/rates/exchange/daily-exchange-rates/)

## 美国默认情景

使用 2026 年七档累进税，单身标准扣除 16,100 美元，MFJ 32,200 美元。工资全部按雇员报酬处理，不对工资本身加征 3.8% NIIT。2027 年先用 2026 年参数，结果字段显式标注 `proxy=true`。截至核验时未核到 IRS/SSA 完整 2027 参数，不把 2026 年报税时在 2027 年申报的表格误称 2027 税率。[IRS 2026 参数](https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill)

雇员 Social Security 为前 184,500 美元的 6.2%，Medicare 全额 1.45%，Additional Medicare 为超过单身 200,000／MFJ 250,000 美元部分的 0.9%。不得扣除雇主承担的另一份工资税。[SSA 2026 Fact Sheet](https://www.ssa.gov/cola/factsheets/2026.html)

当前引擎明确采用标准扣除，不同时加入分项扣除。SALT 参考规则另存：2026 年上限 40,400 美元，MAGI 超 505,000 后按超额的 30% 减少，最低 10,000。高薪球员通常触及最低额，但不能普遍写成所有人的 SALT 上限都是 10,000；以后开放分项扣除还需处理 2026 年 IRC 68 的限制及实际可扣项目。[26 USC 164](https://usc-cdn.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section164&num=0&edition=prelim)

## 安大略默认情景

加拿大联邦和 Ontario 都逐档计算。高收入联邦 BPA 从 16,452 递减至 14,829；基本 CPP 与 EI 产生非退还抵免，增强 CPP 作为收入扣除。Ontario 在基础省税之后另算两档 surtax 和最高 900 CAD Health Premium。全部输入来自 CRA 2026 T4127，详细数值保存在参数 JSON。[CRA T4127](https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/t4127-payroll-deductions-formulas/t4127-jan/t4127-jan-payroll-deductions-formulas-computer-programs.html)

加拿大缴费覆盖采用全年 CPP/EI 情景，不叠加全额美国 FICA。实际雇佣、外派及 coverage certificate 会改变社保归属，需要单独覆盖默认值。[SSA 美加社保协定说明](https://www.ssa.gov/international/Agreement_Pamphlets/canada.html)

2027 年另有已立法待生效的 CPP 基础费率下调：2026 c.22 第 41–43 条拟将基础雇员费率从 4.95% 改为 4.75%，第 44 条规定须 Order in Council 生效；核验时 Justice 页面仍列为未生效修订。当前明确保留 2026 代理参数，不能声称 2027 费率已核定；更新时同时核查生效令、YMPE/YAMPE 与 EI 上限。[修法及生效条款](https://laws-lois.justice.gc.ca/eng/AnnualStatutes/2026_22/page-3.html)、[未生效修订清单](https://lois.justice.gc.ca/eng/acts/C-8/nifnev.html)

## 美加条约是条件判断，不是固定加拿大税率

美加条约 XVI(3) 对两国定期比赛联盟的球队雇员排除一般运动员条款，须回到 XV。XV(2)(b) 检查相关任意 12 个月不超过 183 日、非东道国付款人及非当地 PE 负担报酬。因此，默认美国球队、美国条约居民短期赴加拿大比赛，可能最终免加拿大所得税。对称地，加拿大条约居民效力加拿大球队、赴美履职也可能符合美国联邦豁免。美国公民受 saving clause 影响，不能套用非美国公民的豁免。球队归属不证明个人居民身份。[美加整合协定 XV、XVI、XXIX](https://www.canada.ca/en/department-finance/programs/tax-policy/tax-treaties/country/united-states-america-convention-consolidated-1980-1983-1984-1995-1997-2007.html)

建议 TOR 的首个快答采用“加拿大安大略居民、条约资格及加拿大社保覆盖成立”的明确默认情景。为避开未知公民身份的双重申报，不把该默认值包装为球员本人税单。实际美国公民／美国条约居民方案涉及重新分配收入来源和抵免顺序，须升级为个人情景。

美国州税一般不受上述仅覆盖联邦所得税的条约直接豁免。CRA Folio 1.68 明确：即便美国联邦按条约免税，实际被美国州征税的收入仍可进入加拿大外国税收抵免分子。分子不要盲目放全部美国工作收入，例如没有被任何美国税区征税且联邦免税的收入需要排除。[CRA Folio 1.6、1.68](https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-5-international-residency/folio-2-foreign-tax-credits-deductions/income-tax-folio-s5-f2-c1-foreign-tax-credit.html)

省级抵免只处理联邦未抵免的剩余外国税，并受省税对应收入限额约束。Ontario 计算基数不含后续加入的 Health Premium；2025 ON428 中抵免在第 82 行，健康费在第 89 行。当前用工资比例分摊净收入扣除，未实现所有个性化调整。[T2036](https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2036.html)、[ON428 表](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5006-c/5006-c-25e.pdf)

## 英国、法国和墨西哥

美国条约居民运动员门槛为英国 20,000 USD、法国 10,000 USD、墨西哥 3,000 USD，均须考虑相关报酬及报销。未超过门槛还须满足雇佣条款条件；超过门槛可就全额相关报酬适用东道国税。函数接收单独的报销金额，未知时零值是一项公开假设。[美英第 16 条](https://www.gov.uk/government/publications/usa-tax-treaties/2001-uk-usa-double-taxation-convention-as-amended-by-the-2002-protocol-in-force)、[美法技术解释第 17 条](https://www.irs.gov/pub/irs-trty/francetech.pdf)、[美墨第 18 条](https://www.irs.gov/pub/irs-trty/mexico.pdf)

英国使用 2026–27 England 20%／40%／45% 档位。默认不凭美国居民身份给 UK Personal Allowance；英国／EEA 国籍、其他协定资格可改变结果。若有资格，则采用 12,570 GBP 并按 100,000 GBP 以上每超 2 镑减 1 镑。程序不把 basic-rate 预扣当最终负担。[HMRC 税档](https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past)、[非居民个人免税额资格](https://www.gov.uk/tax-uk-income-live-abroad/personal-allowance)

法国使用最新核到的 2025 收入／2026 申报税档作为显式代理，按单人一份额、工资 10% 职业费用扣除（509–14,555 EUR）估算。最终取累进所得税和非居民最低所得税规则的较高者，再考虑 CEHR；未把仅针对法国居民的 CDHR 加给短期访客。法国官方明确运动员 15% 扣缴**全部非最终结清税**，因此不能按 15% 当最终税后收入。[法国非居民计算及非最终扣缴说明](https://www.impots.gouv.fr/particulier/le-calcul-de-votre-impot)、[税档](https://bofip.impots.gouv.fr/bofip/2491-PGP.html/identifiant=BOI-IR-LIQ-20-10-20260407)、[费用扣除](https://bofip.impots.gouv.fr/bofip/10855-PGP.html/identifiant=BOI-BAREME-000035-20260217)、[CEHR](https://bofip.impots.gouv.fr/bofip/7804-PGP.html/identifiant=BOI-IR-CHR-20170711)

墨西哥按 LISR 第 170 条毛收入 25% 路径估算，不默认有符合条件的净收入选举。工作报酬分摊、费用、协定申报和地方特殊豁免仍是情景输入。[墨西哥所得税法第 170 条](https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf#page=209)

境外所得税计算后，美国居民工资默认适用 general-category 当前年度外国税收抵免，以对应外国来源应税收入占比限制。这里按比例分摊扣除、忽略跨年 carryover 和私人收入，故为明确简化。加拿大条约豁免不意味着把所有加拿大工作收入从美国外国来源收入分子删除；只是不能虚构加拿大已交税。[IRS Publication 514](https://www.irs.gov/publications/p514)

## 赛季金额如何归属两税年

默认 24 次发薪可用当前赛季 1/6 归 2026、5/6 归 2027 的假设。推荐先建立每个税年的年度工资情景，再用当前赛季工资占年度工资比例分配年度税负。2026 年年度工资代理 = 上赛季工资 × 5/6 + 本赛季工资 × 1/6；2027 年缺少下一赛季已知工资时用本赛季全年工资水平作年度代理，再分配 5/6。这属于平均税率归属，不是“有无这份工资的增量税”。

这样避免把赛季分成两份独立年度报酬后重复享受低税档、标准扣除或错误重复 Social Security 上限。必须保留每税年的年度代理、归属比例、税率年份及上一赛季是否缺失。新秀、跨国转会、短约、退役或不同实际发薪安排误差更大，不用不完整公开历史直接声称个人某税年的真实全年收入。

## 已做的计算核验

- 1,000,000 USD 美国单身：联邦 320,000.25，雇员工资税 33,139.00。
- 1,000,000 USD 安大略情景，FX 1.424：联邦 309,401.68 USD，省税 193,243.25，缴费 4,051.63。
- 核对低收入非负、逐档算术、工资税上限、Medicare 门槛、CPP/EI 上限、BPA 最低额、外国税抵免上限以及包含费用时的条约门槛切换。
- 这些是算法回归样例，不是任何球员的税单或保证误差区间。
