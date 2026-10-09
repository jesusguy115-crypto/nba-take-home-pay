# Western / central NBA state tax module

Checked 2026-10-09. Files `tax-west.json` and `tax_west.py` belong together. The module supports Single and married filing jointly (MFJ), for independent taxpayers under 65, with wages only, no dependents, no itemized deductions and no additional income. Personal/taxpayer credits and the Minnesota/Wisconsin marriage credits are implemented. Fact-dependent and refundable credits are outside the input model. These assumptions are computational scenarios, not claims about a named player's private tax return.

## Integration

- `calculate_state(code, gross, year=2026, filing_status="single", spouse_wages=0)` returns annual resident state income tax before cross-state credits, local taxes and payroll contributions.
- `calculate_nonresident(code, gross, share, year=2026, filing_status="single", spouse_wages=0)` uses ordinary full-income liability allocation except that Oregon applies its brackets directly to source taxable income. California computes the separate surtax on source income; Wisconsin allows no nonresident marriage credit in this scenario because the spouse has no Wisconsin-source wages. It does not apply interstate reciprocity or credits.
- `calculate_payroll(base_state, gross, year=2026, residence_state=..., oregon_source_share=...)` returns additional employee payroll charges. Coverage uses a stated employment-base assumption. It does not add employer-only UI, ETT or TriMet payroll taxes.
- `calculate_portland(gross, year=2026, filing_status="single", spouse_wages=0, *, metro_resident=False, multnomah_resident=False, metro_source_share=0, multnomah_source_share=0)` does not guess local residence. Set residency flags explicitly in the scenario. Nonresident thresholds are applied to source taxable income.
- `calculate_portland_resident_credit(...)` applies local other-state credit policy; apply separately for SHS and PFA and each source state, then cap aggregate credits at that local tax.
- `calculate_denver_opt(monthly_denver_wages)` counts months with at least $500 of Denver service earnings and charges the employee $5.75 for each. Mapping or iterable is accepted.

`gross` includes `spouse_wages`; it is total household wages for MFJ. The spouse amount cannot exceed gross, and Single rejects nonzero spouse wages. MFS, head of household and other statuses raise an error. MFJ assumes both spouses share a residence and that spouse wages are earned entirely there. A nonresident `share` is player source wages divided by household wages; the spouse does not follow the player’s travel. Different actual spouse work locations are outside this interface. `calculate_payroll` continues to take only the player’s wages, and employer/employee caps must be applied separately to each employee if modeling an entire household.

Annual tax results include `ordinary_tax`, `surtax`, `credit_base`, `marriage_credit`, `filing_status`, `spouse_wages` and `scope_status`. `credit_base` excludes California Behavioral Health Services Tax. The result's bracket amounts precede personal tax credits. Resident `adjustments` reconcile those and the surtax. On nonresident results, `adjustments_scope` says the inherited adjustments describe the full household calculation; allocated `personal_credit`, `marriage_credit`, `tax_before_credits` and `tax` describe the source result. `bracket_scope` distinguishes Oregon source brackets from the other full-household schedules; `resident_full_income_brackets` preserves the starting calculation.

2027 uses 2026 state parameters as an explicit proxy. Known 2027 changes are incorporated for Metro SHS threshold ($132,000 Single / $211,000 MFJ) and Colorado FAMLI employee rate (0.43%). Minnesota's 2027 employee maximum rate remains 0.44%. Payroll wage caps for 2027 remain labeled 2026 proxies.

## Important implementation choices

### California

FTB's October 2026 Tax News, published September 30, already includes the actual 2026 single rate schedule and $5,900 standard deduction. The older 2025 table should be retired for this scenario. The exemption credit is $158 for 2026. A final 2026 exemption phaseout threshold was not located; the implementation transparently retains the 2025 $252,203 starting threshold, reducing credit by $6 per $2,500 or fraction. At normal full-season NBA salaries this credit is zero under either threshold, so the proxy does not affect those results.

The extra 1% is now named Behavioral Health Services Tax. For a nonresident it applies only to CA-source taxable income exceeding $1 million. For example a $50m annual salary with 1.5% California share has less than $1m sourced taxable income and no such surtax. Applying a full-income surtax times 1.5% would be wrong. California's other-state credit is against ordinary net tax, not this separately computed surtax; exact return credit limitations can still differ from a proportional model.

Sources: [2026 schedule](https://www.ftb.ca.gov/about-ftb/newsroom/tax-news/), [540NR](https://www.ftb.ca.gov/forms/2025/2025-540nr-booklet.html), [Schedule S](https://www.ftb.ca.gov/forms/2025/2025-540-s-instructions.html).

SDI is 1.3% without a wage cap. Employment coverage follows localization, base of operations, direction/control and residence tests in sequence. Do not impose SDI on every visiting player's California game income. The module assumes the CA-based NBA employment is covered on all wages; approved voluntary plans/employer absorption remain unknown.

Sources: [EDD rates](https://edd.ca.gov/en/payroll_taxes/Rates_and_Withholding), [multistate coverage](https://edd.ca.gov/siteassets/files/pdf_pub_ctr/de231d.pdf).

### Oregon and Portland

Oregon's official 2026 estimated-tax publication provides the 4.75/6.75/8.75/9.9% brackets with breakpoints $4,550, $11,400 and $125,000. Its preliminary standard deduction is $2,900; the later wage-withholding publication uses $2,910, which the scenario adopts, explicitly labeled. The $263 personal credit ends above $100,000 AGI single. The federal-income-tax subtraction is zero at $145,000 or more single; below that the module uses wages-only federal liability and the published phaseout bands. This is an income-tax estimate, not the withholding formula with an extra low-wage adjustment.

The statewide employee transit tax remains 0.1%: the current DOR page records the failure of Measure 120. Oregon residents owe it on wages regardless of work location, nonresidents on Oregon work. Paid Leave employee contributions are 0.6% up to $184,500 for 2026 under ordinary covered-employment assumptions. TriMet 0.8237% is an employer tax and must not be deducted from the player.

Metro SHS single threshold is $128,000 for 2026 and $132,000 for 2027. Multnomah PFA is 1.5% above $125,000 and another 1.5% above $250,000; the current Portland page places the next 0.8-point increase in **2028**, not 2027. Residence in Portland/Multnomah cannot be inferred merely from a Blazers contract; default use must be disclosed. A nonresident's thresholds apply to their local source taxable income, so do not allocate a full-world-income local tax by away-day share.

Local credits: Portland's policy defines a resident credit independently for each local tax. Use the lesser of local liability, local liability times mutually taxed modified AGI / total modified AGI, or actual other-state income tax. The policy does **not** instruct subtracting the Oregon state credit from the other-state tax first. Thus a shared depleted credit pool across Oregon, SHS and PFA would not implement this policy. No local credit when the other state grants a nonresident reverse credit; nonresident local filers cannot claim it. The return instructions tie eligibility to claiming an Oregon credit, with a composite-return exception. This still needs exact income/tax facts when leaving the simple wages scenario.

Sources: [Oregon estimate](https://www.oregon.gov/dor/forms/FormsPubs/publication-or-estimate_101-026_2026.pdf), [withholding updates](https://www.oregon.gov/dor/forms/FormsPubs/withholding-tax-formulas_206-436_2026.pdf), [transit](https://www.oregon.gov/dor/programs/businesses/pages/statewide-transit-tax.aspx), [Portland rates](https://www.portland.gov/revenue/personal-tax), [local credit policy](https://www.portland.gov/revenue/policy-credit-taxes-paid-another-state).

### MFJ parameters and marriage credits

These values were checked against official sources on 2026-10-09. Flat rates remain unchanged by filing status. Joint brackets are stored explicitly, not produced by multiplying Single brackets.

| State | MFJ standard deduction / exemption | MFJ taxable-income bracket starts above zero | Other joint rule |
|---|---|---|---|
| CA | $11,800; $316 credit | $22,912 / $54,314 / $85,722 / $118,996 / $150,394 / $768,218 / $921,854 / $1,536,426 | $504,411 AGI credit-phaseout start remains a **2025 proxy**; reduction is $12 per $2,500 or fraction. The 1% surtax threshold stays $1m. |
| OR | $5,820; $526 credit | $9,100 / $22,800 / $250,000 | Credit ends above $200k AGI. Federal subtraction max remains $8,750; joint AGI phaseout starts at $250k in $10k bands and reaches zero at $290k. |
| AZ | $32,200, statutory-index derivation | Flat 2.5% | No charitable contributions assumed. |
| CO | $32,200 | Flat 4.4% | At household AGI above $300k, deduction is capped at $2,000. |
| UT | No deduction from AGI | Flat 4.45% | Credit starts at 6% of $32,200 and decreases by 1.3% of AGI above $36,426, a **2025 phaseout-start proxy**. |
| OK | $12,700 plus $2,000 exemptions | $7,500 / $9,800 / $14,400 | 0%, 2.5%, 3.5%, 4.5%. |
| TX | None | No individual income tax | Same result for Single and MFJ. |
| LA | $25,750 | Flat 3% | Official 2026 estimated deduction. |
| MN | $30,600 | $48,700 / $193,480 / $337,930 | Phaseout starts at $244,400 and $337,800 for both Single and MFJ; joint deduction floor $6,120. |
| WI | Up to $25,840 plus $1,400 exemptions | $20,150 / $69,260 / $443,630 | Deduction loses 19.778% of AGI above $29,040 and becomes zero at $159,690. |
| IL | No standard deduction; $5,850 exemptions | Flat 4.95% | Exemptions disappear above $500k joint AGI. |

Minnesota’s marriage credit is the positive difference between joint tax and two Single-schedule taxes. The lower earner’s wage base subtracts $15,300, half the **unphased** joint deduction; the other base is joint taxable income minus that amount. The code uses the statutory continuous formula and labels the difference from the final rounded M1MA lookup table. Nonresident credit is prorated. [Statute 290.0675](https://www.revisor.mn.gov/statutes/cite/290.0675).

Wisconsin’s credit is 3% of the lower spouse’s qualified earned wages, capped at $16,000 of wages ($480 credit). A zero-wage spouse yields zero. For a nonresident, the statute requires **each spouse’s Wisconsin wages**. This interface assumes zero spouse wages in a nonresident state, so its Wisconsin marriage credit is zero. Multiplying the resident $480 credit by the source share would be wrong, as shown by [2025 Form 1NPR Schedule 2, page 4](https://www.revenue.wi.gov/TaxForms2025/2025-Form1NPR.pdf). Deferred compensation does not qualify merely because it appears on a W-2; guaranteed or waived-player payments require an earned-income classification before claiming this credit. [Form 1 instructions, page 21](https://www.revenue.wi.gov/TaxForms2025/2025-Form1-inst.pdf).

Joint SHS thresholds are $205,000 in 2026 and $211,000 in 2027; joint PFA thresholds are $200,000 and $400,000. They do not double the Single thresholds. See [Portland’s table](https://www.portland.gov/revenue/personal-tax).

Additional joint sources: [CA FTB schedule and deduction](https://www.ftb.ca.gov/about-ftb/newsroom/tax-news/), [CA exemption worksheet](https://www.ftb.ca.gov/forms/2025/2025-540-booklet.html), [OR 2026 withholding indexed figures, pages 6–7](https://www.oregon.gov/dor/forms/FormsPubs/withholding-tax-formulas_206-436_2026.pdf), [OK official deductions/exemptions, pages 10 and 25](https://oklahoma.gov/content/dam/ok/en/tax/documents/forms/individuals/current/511-Pkt.pdf), [Utah credit phaseout, page 9](https://files.tax.utah.gov/tax/train/webinars/2026-01-15-presentation.pdf), [IL AGI limits](https://tax.illinois.gov/content/dam/soi/en/web/tax/research/publications/bulletins/documents/2024/fy-2024-02.pdf). Other state sources appear immediately below.

### Oregon nonresident correction

The former implementation incorrectly multiplied full-income Oregon tax by the source share. The final [2025 Form OR-40-N, pages 6–7](https://www.oregon.gov/dor/forms/FormsPubs/form-or-40-n_101-048_2025.pdf) computes source income less proportional deductions on line 45, then applies the tax chart on line 46. [Final OR-40-NP instructions, page 21](https://www.oregon.gov/dor/forms/FormsPubs/form-or-40-n_or-40-p-inst_101-048-1_2025.pdf) require proportional deductions; page 23 prorates the exemption credit. The tax-times-percentage step on page 22 applies only to part-year Form OR-40-P. The corrected full-year nonresident helper changes Single cached estimates as well as MFJ estimates. For $1m wages and 1% Oregon share, 2026 ordinary source tax changes from $969.5541 to $582.03575.

### Low-income and income-character boundaries

All modeled nonrefundable credits stop at zero liability. No negative taxable income or negative tax is produced. Household wages below $80,000 receive `scope_status="proxy_before_unmodeled_refundable_or_fact_dependent_credits"`; this is a deliberately broad model-screening bound, not a legal threshold. Such outputs exclude potential earned-income, working-family, rental, property and other refundable/fact-dependent credits. They are a tax-before-those-credits proxy, not a completed low-income net tax estimate. At zero wages the modeled wage tax is zero, but potential non-wage benefits are still outside scope. The under-65/no-dependent assumptions apply to both spouses. For waived, deferred or other unusual payment character, do not infer earned-income-credit eligibility from the gross amount alone.

### Other high-income changes

- Colorado AGI above $300,000 single has only $1,000 of standard/itemized deduction retained in 2026, rather than the old $12,000 limit. Statutory rate is 4.4%. [Official guide](https://tax.colorado.gov/individual-income-tax-guide).
- Utah rate is 4.45% from January 2026. Tax base is modified federal AGI, with a taxpayer tax **credit**, not a subtraction of the federal standard deduction. At NBA income the credit is zero. The low-income credit's 2025 phaseout start remains labeled a proxy. [Enacted rate](https://le.utah.gov/xcode/title59/chapter10/C59-10-S104_2026050620260506.pdf).
- Oklahoma enacted the new 2026 0/2.5/3.5/4.5% schedule. Standard deduction $6,350 and personal exemption $1,000 are separate reductions. [Tax Commission legislation summary](https://oklahoma.gov/content/dam/ok/en/tax/documents/resources/publications/legislation/2025LegislativeUpdate.pdf).
- Louisiana official 2026 estimated-tax worksheet uses $12,875 single deduction and 3% flat tax. It is marked an official estimated deduction pending final-return publication. [IT-540ES](https://dam.ldr.la.gov/taxforms/IT540ESi-2026.pdf).
- Minnesota standard deduction is $15,300 before high-income limitation. The implemented 3%/10% limitation caps the reduction at 80%, usually leaving $3,060 for an NBA player. [2026 indexed parameters](https://www.revenue.state.mn.us/sites/default/files/2025-12/inflation-adjusted-amounts-2026.pdf), [phaseout statute](https://www.revisor.mn.gov/statutes/cite/290.0123).
- Wisconsin deduction shrinks to zero at high income; the $700 personal exemption remains. Its nonresident rate brackets are prorated, explaining why a full-income effective-rate source allocation is suitable for this simplified wages-only scenario. [2026 WT-4A](https://www.revenue.wi.gov/TaxForms2017through2019/w-234f.pdf).
- Illinois has no standard deduction. The 2026 $2,925 exemption disappears above $250,000 AGI single. Flat rate 4.95%. [2026 bulletin](https://tax.illinois.gov/content/dam/soi/en/web/tax/research/publications/bulletins/documents/2026/fy-2026-15.pdf).
- Arizona uses 2.5%; $16,100 scenario deduction follows the current statute's federal-style inflation rule and the IRS 2026 amount. It is labeled statutory-index derived, because a final 2026 return was not located. [A.R.S.43-1041](https://www.azleg.gov/ars/43/01041.htm).

## Credit / athlete sourcing boundaries

Reverse-credit pairs CA–OR, CA–AZ, OR–AZ claim on the **nonresident work-state return** in either direction. California no longer treats Indiana as reverse since 2017. Oregon's list additionally includes Indiana and Virginia. Source JSON has directed eligibility sets, not an indiscriminate clique. Both states' sourcing rules and credit limits still need applying.

Illinois official Publication 130 lists reciprocity for IA/KY/MI/WI and separately explains athlete duty-day allocation. No primary authority was found supporting a blanket exclusion of NBA athletes from these wage reciprocity agreements. Do not confuse athlete exceptions to short-work-stay thresholds with exclusions from wage reciprocity. [Illinois guidance](https://tax.illinois.gov/research/publications/pubs/who-is-required-to-withhold-illinois-income-tax/withholding-illinois-income-tax-for-my-employees.html).

The module's general nonresident allocation is a disclosed approximation, not a statement that all states adopt the same duty-day definition. Oregon disabled-list presumptions, individual rehabilitation activities, playoff days, travel-only days and G League assignments can change numerator or denominator. A real personal duty-day ledger remains necessary for exact returns. [Oregon athlete rule](https://secure.sos.state.or.us/oard/view.action?ruleNumber=150-316-0175).

## Independent numeric checks completed

Compared progressive integration to independently published cumulative tax amounts at statutory table breakpoints:

| Case | Published ordinary tax | Module |
|---|---:|---:|
| CA taxable income $768,213 (gross $774,113) | $74,675.27 | $74,675.268, rounds to $74,675.27 |
| WI taxable income $332,720 (gross $333,420) | $17,030.62 | $17,030.62 |
| OK taxable income $7,200 (gross $14,550) | $109.25 | $109.25 |

California difference of two mills results from the published table's cent rounding; no user-visible significance. California nonresident $50m gross / 1.5% source share correctly produces **zero** 1% surtax. Portland policy's published Jim example ($2,000 local tax, $40,000 modified AGI, $4,000 mutual income and $100 Idaho tax) produces a $100 credit in the helper. No statistical precision interval is implied by any of these checks.


## Integration audit — resident credits and wage reciprocity (2026-10-09)

The following corrections are implemented in `scripts/estimate.py` and registered in the script JSON sources. All are within the disclosed wages-only source-share model; a completed return can require additional allocation adjustments.

- **Illinois:** Schedule CR takes one aggregate credit limit. It includes eligible US state and local income taxes. The Column B wage ratio follows Illinois sourcing, excludes reciprocal-state employee wages unless those wages bear a local tax, and retains other non-Illinois wage sources even if their jurisdiction levies no wage tax. Foreign income taxes never enter the qualifying tax pool. Line 43 rounds the ratio to three decimals. The credit is distributed among source jurisdictions proportionally only for display. [Schedule CR instructions](https://tax.illinois.gov/forms/incometax/currentyear/individual/il-1040-schedule-cr-instr.html), [form lines 43 and 51–55](https://tax.illinois.gov/content/dam/soi/en/web/tax/forms/incometax/documents/currentyear/individual/il-1040-schedule-cr.pdf).
- **Wisconsin:** Local net income tax paid directly to a state can qualify. The modeled Indiana county tax is eligible even when the state wage tax is exempt under reciprocity. Directly paid municipal taxes such as Philadelphia are not treated as eligible. [Publication 125, January 2026, p5, Indiana example](https://www.revenue.wi.gov/DOR%20Publications/pb125.pdf).
- **Michigan:** The state resident credit includes qualifying taxes paid to local governments outside Michigan, including local taxes in reciprocal states. [Treasury guidance](https://www.michigan.gov/en/taxes/questions/iit/accordion/residency/are-my-wages-earned-in-another-state-taxable-in-michigan-if-i-am-a-michigan-resident-1).
- **Georgia:** Combine mutually taxed income and final tax from all other US states into one limit; include eligible US local net income tax. Source shares remain an approximation to each return's income computation. [Rule560-7-7-.01(1)](https://rules.sos.ga.gov/gac/560-7-7), [IT-511 p34](https://dor.georgia.gov/document/document/2025-it-511-individual-income-tax-booklet/download).
- **Indiana reverse credit direction:** Indiana gives its nonresident credit to qualifying AZ/OR/DC residents; it is not limited to reverse credits claimed in AZ or OR. This matters for Oregon residents: the Indiana income does not produce an Oregon resident credit or Portland resident credit in the modeled reverse-credit case. The directed map now includes `IN: [AZ, OR, DC]`. [Current Bulletin28](https://www.in.gov/dor/files/reference/ib28.pdf).

### Athlete reciprocity conclusion

`WEST_RECIP` has the correct lists: IL with IA/KY/MI/WI; WI with IL/IN/KY/MI; MN with MI/ND. No primary authority located excludes employee NBA wages categorically from these agreements. Athlete duty-day rules and exclusions from a short-work-stay threshold do not cancel wage reciprocity.

Wisconsin's specified exceptions concern residency and nonemployee income, including Illinois/Indiana/Kentucky dual-residency cases. Minnesota reciprocity also requires returning to the resident state **at least once each month**. The base-team-residence scenario assumes that qualification; a user who sets a different resident state must confirm it. The calculator does not establish actual domicile, dual residence or off-season return visits. This is a remaining eligibility assumption, not a finding about any named player. Minnesota explicitly disallows credits for city/county/school-district tax; the state calculation therefore continues to exclude such local taxes.

Sources: [WI Publication121 January2026](https://www.revenue.wi.gov/DOR%20Publications/pb121.pdf), [IL Publication130 athlete sourcing and reciprocal exemption](https://tax.illinois.gov/research/publications/pubs/who-is-required-to-withhold-illinois-income-tax/withholding-illinois-income-tax-for-my-employees.html), [MN reciprocity Fact Sheet4](https://www.revenue.state.mn.us/reciprocity-income-tax-fact-sheet-4), [MN other-state credit scope](https://www.revenue.state.mn.us/taxes-paid-another-state-credit).

### Focused integration checks

Annual gross $10m, 2026 parameters, source shares supplied directly:

| Scenario | Verified modeled amount |
|---|---:|
| WI resident, 10% Indiana/Marion wages | $20,200 county tax credited against Wisconsin |
| MI resident, 10% Cleveland wages | $25,000 Ohio city tax credited despite reciprocal state wage exemption |
| IL resident, 10% California +10% Texas wages | $99,000 aggregate ceiling, versus incorrect $49,500 per-CA-only ceiling |
| IL resident, 10% Detroit wages | $11,992.80 local tax credit (the city module includes $600 exemption) |
| GA resident, 10% California +10% Arizona, plus10% untaxed Texas | $99,650.30 combined limit on the 20% mutually taxed income |
| Portland resident, 10% Indiana wages | $29,497.05 work-state reverse credit; no Portland resident credit for that income |
| CA employment payroll | $130,000 SDI |
| OR employment and residence payroll | $11,107, consisting of $1,107 Paid Leave plus $10,000 transit |
| MN employment payroll | $811.80 employee Paid Leave |

Payroll localization integration was consistent with the stated base-of-operations assumption. The itinerary denominator and half-day weights are explicitly hypothetical; this audit does not certify them as any state's legal duty-day calculation.


## Single/MFJ regression checks (2026-10-09)

Run `python3 scripts/tax_west.py`. This checks independent statutory-table examples, all eleven states at zero / $1,000 / $20,000 / $80,000 / $200,000 / $10m, source-share endpoints, validation failures and payroll per employee. Selected fixed results are below.

| 2026 scenario | Verified result |
|---|---:|
| CA MFJ gross $111,800, taxable $100,000 | $2,654.16 tax after $316 credit |
| CO MFJ $300,000 / $300,001 gross | $11,783.20 / $13,112.044 |
| IL MFJ $500,000 / $500,001 gross | $5,850 / $0 personal exemption |
| MN MFJ $200,000, one wage earner | $10,813.05 |
| MN MFJ $200,000, each earns $100,000 | $10,553.21; $259.84 marriage credit |
| WI MFJ $100,000, each earns $50,000 | $480 marriage credit, deduction $11,805.5312 |
| WI MFJ $1m, equal spouses, 1% household WI source share, spouse works only at residence | $0 marriage credit; $651.62905 source tax |
| OR MFJ $100,000 gross | $7,640 federal subtraction plus $5,820 standard deduction |
| OR Single $1m gross, 1% source | $582.03575 source tax |
| Portland MFJ $500,000 taxable, resident of both districts | $8,950 in 2026; $8,890 in 2027 |
| CA MFJ $1,000,000 / $1,000,100 taxable | $0 / $1 BHS surtax |

The checks also reject MFS, spouse wages greater than household wages, negative or nonfinite spouse wages, and nonzero spouse wages in Single. They verify `share=0` yields zero source tax and, with no spouse source-income conflict, `share=1` agrees with the corresponding resident calculation. These are deterministic implementation checks, not real-return accuracy validation.
