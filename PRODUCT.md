# NBA Take-Home Pay

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing offline Python 3.9+ skill. The user approved portable interactive HTML alongside tables. Use a reusable HTML/CSS/JavaScript template with embedded data and fonts; no server, API key or JavaScript dependency required for readers.

## Users

Chinese-speaking NBA readers asking for fast estimates, comparisons and rankings. Other agents install the same public skill and must reproduce the result.

## Product Purpose

Query 2026–27 NBA after-tax contract-income estimates from cached Spotrac cash salaries and the existing tax model. The visualization and table must use exactly the same result and assumptions.

## Capabilities and Constraints

- Existing age, birth-decade, team, filing and settlement filters remain authoritative.
- Clearly show non-roster retained payments and identify payer teams. Non-roster does not prove retirement.
- No-state-income-tax badges, filing assumptions, salary and age dates, and uncertain league settlement remain visible.
- Model estimates are not bank deposits; do not invent live data, confidence intervals or audited accuracy.
- A chart switches measures and order within the returned roster only; it never implies a new league-wide selection.

## Brand Commitments

Approved in conversation: dark graphite, warm white, restrained gold; refined Chinese sans-serif typography and aligned financial numerals; horizontal ranking bars with restrained animation and interactive detail.

## Evidence on Hand

`skills/nba-take-home-pay/assets/` contains the salary, tax result, name and birthday snapshots. A real demonstration uses the ten lowest estimated net incomes among recipients aged 35 or older, including visibly labeled retained payments.

## Product Principles

- Show the answer before explanation.
- Preserve scope and uncertainty at every view.
- Keep ordinary queries offline and fast.
- Generate the table and visual from one result, with a portable artifact fallback.

## 合同与身份呈现

球员头像为前景主视觉，放大并压暗的当前球队 Logo 作背景，取消角落小徽标；当前合同规模紧邻身份，未来续约独立标识。详情和 PNG 保留合同总额、保障、平均年薪、赛季及核查日期。未核实不伪造；来源旧球衣不覆盖薪资快照球队。
