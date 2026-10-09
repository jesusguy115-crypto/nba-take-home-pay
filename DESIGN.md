---
name: Courtside Ledger
description: Offline Chinese NBA salary estimates with a synchronized ranking chart and ledger.
colors:
  bg: "#111416"
  surface: "#191d20"
  hover: "#23282b"
  ink: "#f2ede3"
  muted: "#afb5b8"
  gold: "#d7b878"
  line: "#343a3d"
  green: "#9ac5ba"
  retained: "#a7afb7"
typography:
  headline:
    fontFamily: "'Ledger Han', 'PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.36
  body:
    fontFamily: "'Ledger Han', 'PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "'Ledger Han', 'PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.65
  amount:
    fontFamily: "'Ledger Numbers', sans-serif"
    fontSize: "25px"
    fontWeight: 500
    lineHeight: 1.1
  total:
    fontFamily: "'Ledger Numbers', sans-serif"
    fontSize: "46px"
    fontWeight: 500
    lineHeight: 1.2
rounded:
  bar: "2px"
  status: "3px"
  control: "5px"
spacing:
  inline: "8px"
  control-gap: "14px"
  row-gap: "15px"
  section: "24px"
components:
  metric-active:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.bg}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
  metric-idle:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
  order-select:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 27px 8px 10px"
  status-label:
    rounded: "{rounded.status}"
    padding: "0 5px"
  chart-row:
    textColor: "{colors.ink}"
    padding: "13px 0"
  net-total:
    textColor: "{colors.gold}"
    typography: "{typography.total}"
---
# Design System: Courtside Ledger

## Overview

**Creative North Star: "Courtside Ledger"**

Courtside Ledger presents Chinese NBA salary estimates as a readable financial ledger. Dark graphite, warm white and restrained gold support horizontal ranking bars, aligned amounts and explicit roster status.

The same result drives the chart and table. Embedded Chinese and numeric fonts preserve the presentation offline; labels and calculation assumptions remain visible alongside the amounts.

**Key Characteristics:**
- Graphite surfaces with warm white text and restrained gold emphasis.
- Chinese sans-serif labels paired with condensed, tabular financial numerals.
- Flat ledger rows, visible status labels and a synchronized data table.

## Colors

### Primary

Restrained gold marks the selected metric, active values, totals, source links and active-player bars.

### Secondary

Soft green identifies the no-state-income-tax designation. Its meaning is always accompanied by text.

### Neutral

Graphite background and slightly lighter surfaces distinguish the canvas from selected rows and controls. Warm white carries primary information; muted gray carries explanatory labels. The line tone separates ledger sections. Retained-payment bars use a gray dashed outline and a darker fill, accompanied by explicit status text.

## Typography

Ledger Han is the embedded Noto Sans SC subset. Ledger Numbers is the embedded Barlow Semi Condensed font. Both are bundled with OFL notices. Amounts use tabular numerals; the exact desktop roles are defined in frontmatter.

The main heading uses tight tracking (-.025em). Its gold subtitle is lighter and smaller (26px, weight 400). Desktop player names use 15px at weight 500; they change to 14px at 1120px, 16px at 900px, 14px at 600px and 13px at 370px. Supporting copy stays at least 12px. At 600px, the heading becomes 27px and the total becomes 43px. Keep currency units adjacent to amounts.

## Layout

A centered shell has a maximum width of 1360px and desktop padding of 32px 48px 28px. The ranking area and a 286px detail column form a two-column grid with a 34px gap. The detail column is sticky, 24px from the top. Rank, name, bar and value form consistent aligned columns; their desktop widths are 30px, 196px, flexible and 84px, separated by 15px.

At 1120px the shell uses 30px side padding and the detail column contracts to 254px. At 900px, details move below the chart in two columns. At 600px, details stack, controls fill the width, and the shell uses 18px side padding. At 370px, side padding becomes 13px. At 1550px, top padding grows to 42px. The data table independently scrolls horizontally with a 1030px minimum width. On small screens, controls have at least 44px height, except replay at 40px.

## Elevation & Depth

There are no shadows. Tonal surfaces, thin rules and a left divider establish hierarchy. Selection changes the row surface and highlights its rank and amount. Print switches to a light paper palette and removes interactive controls.

## Shapes

Small, functional corners keep the ledger compact. Bars use the bar radius, status badges use the status radius and controls use the control radius. Rows and account sections remain flat and separated by fine rules. Retained-payment bars have a dashed border; active-player bars are solid gold.

## Components

Metric buttons use gold fill for the pressed state, transparent fill otherwise and the hover surface for idle hover. Sorting uses a native select. Replay is a gold text button with an understated bottom rule. Keyboard focus receives a 2px gold outline with 5px offset.

Ranking rows are buttons with a minimum desktop height of 74px, increasing to 83px at 600px. Hover and keyboard focus preview the account details; clicking preserves selection. A mobile selection scrolls to the detail panel. The account total emphasizes the estimated net amount while keeping its unit and filing scenario visible. Status badges distinguish active and retained-payment records in chart and detail views.

The bar width and position transition for 650ms with cubic-bezier(.16,1,.3,1). Sorting movement takes 520ms with the same easing; counting runs for 650ms with a quartic ease-out. Control and row surface transitions take 180ms. Reduced-motion mode removes animations, transitions and replay, and displays final values directly.

The table mirrors the chart ordering and highlights the current monetary column. It remains populated without JavaScript. Empty results show an explanatory message and disable controls.

## Do's and Don'ts

### Do:
- Keep chart and table values, selection scope and ordering consistent.
- Keep monetary units, roster status, snapshot dates and settlement assumptions visible.
- Embed the bundled fonts and honor reduced-motion preferences.

### Don't:
- Do not imply that a metric switch selects a new league-wide roster.
- Do not equate retained payments with confirmed retirement.
- Do not replace explicit status labels with color alone.
