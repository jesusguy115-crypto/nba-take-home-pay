"""Auditable wage-only US / Ontario scenarios; no network or external packages.

2027 requests deliberately reuse 2026 law and return that fact. These functions
calculate annualized scenarios, not a player's actual return or bank deposits.
All Canadian output amounts are USD unless the key ends in ``_cad``.
"""
from __future__ import annotations

import math

RULE_YEAR = 2026
USD_CAD = 1.4240  # Bank of Canada, 2026-10-08; scenario FX, not a yearly average.
SOURCES = {
    "us_brackets": "https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill",
    "us_payroll": "https://www.ssa.gov/cola/factsheets/2026.html",
    "us_additional_medicare": "https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax",
    "ca_rates": "https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/t4127-payroll-deductions-formulas/t4127-jan/t4127-jan-payroll-deductions-formulas-computer-programs.html",
    "ca_foreign_credit": "https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-5-international-residency/folio-2-foreign-tax-credits-deductions/income-tax-folio-s5-f2-c1-foreign-tax-credit.html",
    "ca_provincial_credit": "https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2036.html",
    "us_ca_treaty": "https://www.canada.ca/en/department-finance/programs/tax-policy/tax-treaties/country/united-states-america-convention-consolidated-1980-1983-1984-1995-1997-2007.html",
    "fx": "https://www.bankofcanada.ca/rates/exchange/daily-exchange-rates/",
    "us_foreign_credit": "https://www.irs.gov/publications/p514",
}

US_BRACKETS = {
    "single": [(12400, .10), (50400, .12), (105700, .22), (201775, .24),
               (256225, .32), (640600, .35), (None, .37)],
    "mfj": [(24800, .10), (100800, .12), (211400, .22), (403550, .24),
            (512450, .32), (768700, .35), (None, .37)],
}
CA_FEDERAL = [(58523, .14), (117045, .205), (181440, .26),
              (258482, .29), (None, .33)]
ONTARIO = [(53891, .0505), (107785, .0915), (150000, .1116),
           (220000, .1216), (None, .1316)]


def _amount(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Income and tax amounts must be finite and non-negative")
    return value


def _year(year):
    if int(year) not in (2026, 2027):
        raise ValueError("Only 2026 rules and an explicit 2027 proxy are supported")
    return int(year)


def progressive(income, bands):
    """Return exact progressive total and an inspectable tax-band ledger."""
    income = _amount(income)
    rows, total, lower = [], 0.0, 0.0
    for upper, rate in bands:
        taxable = max(0.0, min(income, upper if upper is not None else income) - lower)
        band_tax = taxable * rate
        rows.append({"lower": lower, "upper": upper, "rate": rate,
                     "taxable": taxable, "tax": band_tax})
        total += band_tax
        if upper is None or income <= upper:
            break
        lower = upper
    return total, rows


def calculate_us(gross, year=2026, filing_status="single", spouse_wages=0):
    """US resident wage-only scenario, standard deduction, no dependants.

    ``gross`` is household wages, INCLUDING ``spouse_wages`` for MFJ. Payroll
    taxes retain each worker's Social Security cap. Additional Medicare is a
    household liability; its per-person wage-proportional split is an explicit
    attribution convention, not separate tax returns or employer withholding.
    Filing status and spouse wages are scenario inputs, not verified facts.
    Salary is not investment income, so no 3.8% NIIT is imposed here.
    """
    year, gross = _year(year), _amount(gross)
    spouse_wages = _amount(spouse_wages)
    if filing_status not in US_BRACKETS:
        raise ValueError("filing_status must be single or mfj")
    if filing_status == "single" and spouse_wages:
        raise ValueError("single filing_status cannot include spouse_wages")
    if spouse_wages > gross:
        raise ValueError("spouse_wages is included in gross and cannot exceed it")
    primary_wages = gross - spouse_wages
    deduction = 16100.0 if filing_status == "single" else 32200.0
    threshold = 200000.0 if filing_status == "single" else 250000.0
    taxable = max(0.0, gross - deduction)
    federal, bands = progressive(taxable, US_BRACKETS[filing_status])
    additional_medicare = max(0.0, gross - threshold) * .009
    payroll_by_person = {}
    for person, wages in (("primary", primary_wages), ("spouse", spouse_wages)):
        person_ss = min(wages, 184500.0) * .062
        person_medicare = wages * .0145
        person_additional = additional_medicare * wages / gross if gross else 0.0
        payroll_by_person[person] = {
            "wages": wages, "social_security_wage_base": min(wages, 184500.0),
            "social_security": person_ss, "medicare": person_medicare,
            "additional_medicare": person_additional,
            "payroll": person_ss + person_medicare + person_additional,
        }
    social_security = sum(row["social_security"] for row in payroll_by_person.values())
    medicare = gross * .0145
    payroll = social_security + medicare + additional_medicare
    return {
        "currency": "USD", "year": year, "rules_year": RULE_YEAR,
        "proxy": year != RULE_YEAR, "filing_status": filing_status,
        "gross": gross, "household_wages": gross,
        "primary_wages": primary_wages, "spouse_wages": spouse_wages,
        "deduction": min(gross, deduction),
        "deduction_type": "standard", "taxable_income": taxable,
        "federal": federal, "federal_before_foreign_credit": federal,
        "brackets": bands, "social_security": social_security,
        "medicare": medicare, "additional_medicare": additional_medicare,
        "social_security_cap_per_person": 184500.0,
        "additional_medicare_household_threshold": threshold,
        "payroll_by_person": payroll_by_person,
        "additional_medicare_person_allocation": "household_liability_proportional_to_wages",
        "payroll": payroll, "tax": federal + payroll,
        "net_before_state_local_foreign": gross - federal - payroll,
        "sources": [SOURCES["us_brackets"], SOURCES["us_payroll"],
                    SOURCES["us_additional_medicare"]],
        "assumptions": [
            "US tax resident wage-only annualized scenario; no endorsements or investments",
            "Gross includes the explicit spouse_wages input; default zero is a scenario assumption, not a spouse-income finding",
            "Standard deduction, no itemized SALT/mortgage/charitable deductions or personal credits",
            "Employee share of US FICA; employer contributions are not deducted from salary",
            "Social Security cap applies separately to each worker; MFJ Additional Medicare applies to household wages above $250,000",
            "Additional Medicare per-person amounts allocate household liability in proportion to wages; not actual withholding or separate legal liabilities",
            "2027 uses 2026 parameters" if year == 2027 else "2026 parameters",
        ],
    }


def _ontario_health(taxable):
    if taxable <= 20000:
        return 0.0
    if taxable <= 36000:
        return min(300.0, .06 * (taxable - 20000))
    if taxable <= 48000:
        return min(450.0, 300 + .06 * (taxable - 36000))
    if taxable <= 72000:
        return min(600.0, 450 + .25 * (taxable - 48000))
    if taxable <= 200000:
        return min(750.0, 600 + .25 * (taxable - 72000))
    return min(900.0, 750 + .25 * (taxable - 200000))


def calculate_canada(gross_usd, year=2026, fx=USD_CAD):
    """Ontario resident, single, employed full year under CPP/EI coverage.

    Covers progressive federal/provincial tax, BPA taper, base CPP/EI credits,
    enhanced CPP deductions, Ontario surtaxes, and Ontario Health Premium.
    Treaty entitlement, actual coverage certificate and foreign credits are
    separate inputs. Do not add a second US FICA charge by default.
    """
    year, gross_usd, fx = _year(year), _amount(gross_usd), _amount(fx)
    if fx == 0:
        raise ValueError("fx must be positive CAD per USD")
    gross = gross_usd * fx
    cpp_base = .0495 * max(0.0, min(gross, 74600) - 3500)
    cpp_additional = .01 * max(0.0, min(gross, 74600) - 3500)
    cpp_second = .04 * max(0.0, min(gross, 85000) - 74600)
    ei = .0163 * min(gross, 68900)
    deduction = cpp_additional + cpp_second
    taxable = max(0.0, gross - deduction)
    bpa = 16452 - min(1623.0, max(0.0, taxable - 181440) * 1623 / 77042)
    employment_amount = min(gross, 1501.0)
    f_gross, f_bands = progressive(taxable, CA_FEDERAL)
    f_credit = .14 * (bpa + cpp_base + ei + employment_amount)
    federal = max(0.0, f_gross - f_credit)
    p_gross, p_bands = progressive(taxable, ONTARIO)
    p_credit = .0505 * (12989 + cpp_base + ei)
    p_basic = max(0.0, p_gross - p_credit)
    surtax = .20 * max(0.0, p_basic - 5818) + .36 * max(0.0, p_basic - 7446)
    reduction = min(p_basic + surtax, max(0.0, 600 - p_basic - surtax))
    p_before_health = max(0.0, p_basic + surtax - reduction)
    health = _ontario_health(taxable)
    provincial = p_before_health + health
    payroll = cpp_base + cpp_additional + cpp_second + ei
    cad = {
        "gross": gross, "taxable_income": taxable,
        "enhanced_cpp_deduction": deduction, "federal_bpa": bpa,
        "federal_before_credits": f_gross, "federal_nonrefundable_credits": f_credit,
        "federal": federal, "ontario_before_credits": p_gross,
        "ontario_nonrefundable_credits": p_credit, "ontario_basic": p_basic,
        "ontario_surtax": surtax, "ontario_tax_reduction": reduction,
        "ontario_health_premium": health, "provincial": provincial,
        "cpp_base": cpp_base, "cpp_additional": cpp_additional,
        "cpp_second": cpp_second, "ei": ei, "payroll": payroll,
        "income_tax": federal + provincial, "tax": federal + provincial + payroll,
    }
    return {
        **{key: value / fx for key, value in cad.items()},
        "currency": "USD", "calculation_currency": "CAD", "fx_cad_per_usd": fx,
        "fx_date": "2026-10-08" if fx == USD_CAD else "user_assumption",
        "year": year, "rules_year": RULE_YEAR, "proxy": year != RULE_YEAR,
        "filing_status": "single", "residency_scenario": "Canada_Ontario_resident",
        "breakdown_cad": cad, "federal_brackets_cad": f_bands,
        "ontario_brackets_cad": p_bands,
        "net_before_foreign_tax_and_credit": gross_usd - cad["tax"] / fx,
        "provincial_foreign_credit_base": p_before_health / fx,
        "sources": [SOURCES["ca_rates"], SOURCES["fx"]],
        "assumptions": [
            "Canadian/Ontario resident wage-only scenario, single, no dependants",
            "Full-year CPP/EI coverage with no US FICA duplication; actual social-security coverage may differ",
            "No RRSP, charitable, agent-fee or other individualized deductions",
            "FX is a fixed scenario rate, not the unknown 2026/2027 annual average",
            "2027 uses 2026 parameters" if year == 2027 else "2026 parameters",
        ],
    }


def us_foreign_tax_credit(federal_tax, foreign_tax_paid, foreign_income, gross_income):
    """Wage-only general-category FTC estimate with proportional deductions.

    Input is qualifying FINAL foreign income tax, never a second withholding
    deduction. The general-category foreign basket is aggregated, excluding
    treaty-exempt Canadian-source wages from the tax-paid input. No carryovers.
    """
    federal_tax, foreign_tax_paid = _amount(federal_tax), _amount(foreign_tax_paid)
    foreign_income, gross_income = _amount(foreign_income), _amount(gross_income)
    fraction = min(1.0, foreign_income / gross_income) if gross_income else 0.0
    limit = federal_tax * fraction
    credit = min(foreign_tax_paid, limit)
    return {"credit": credit, "limit": limit, "foreign_income_fraction": fraction,
            "uncredited_foreign_tax": foreign_tax_paid - credit,
            "method": "general_category_current_year_proportional_wage_scenario",
            "source": SOURCES["us_foreign_credit"]}


def canada_foreign_tax_credit(canada_result, foreign_tax_paid, foreign_income):
    """Per-country Canadian wage-only credit estimate, USD throughout.

    Aggregate US state/local income tax by COUNTRY before calling. A treaty-
    exempt US federal wage can still support credit for US state income tax
    (CRA Folio paragraph 1.68). No payroll taxes are passed as income taxes.
    Provincial base conservatively excludes Ontario Health Premium because
    T2036 computes credit before that later ON428 item.
    """
    foreign_tax_paid, foreign_income = _amount(foreign_tax_paid), _amount(foreign_income)
    gross = canada_result["gross"]
    fraction = min(1.0, foreign_income / gross) if gross else 0.0
    federal_limit = canada_result["federal"] * fraction
    federal_credit = min(foreign_tax_paid, federal_limit)
    residual = foreign_tax_paid - federal_credit
    provincial_limit = canada_result["provincial_foreign_credit_base"] * fraction
    provincial_credit = min(residual, provincial_limit)
    return {"federal_credit": federal_credit, "federal_limit": federal_limit,
            "provincial_credit": provincial_credit, "provincial_limit": provincial_limit,
            "credit": federal_credit + provincial_credit,
            "uncredited_foreign_tax": residual - provincial_credit,
            "foreign_income_fraction": fraction,
            "method": "per_country_current_year_proportional_wage_scenario",
            "sources": [SOURCES["ca_foreign_credit"], SOURCES["ca_provincial_credit"]]}


def calculate_overseas(country, allocated_usd, year=2026, *,
                       us_treaty_resident=True, uk_personal_allowance=False,
                       allocated_expenses_usd=0):
    """Illustrative final income tax on a short US-team overseas visit.

    The caller supplies a separately sourced wage allocation; no claim that a
    state's duty-day denominator is the host country's exact sourcing rule.
    Treaty thresholds include reimbursed expenses, hence the separate input.
    Canadian exemption assumes US-team employer, treaty residence, <=183 days
    in any relevant twelve-month period and no Canadian PE bearing wages.
    Neither French 15% withholding nor UK basic-rate withholding is treated as
    a second final tax. Fixed FX snapshot and current-law proxies are explicit.
    """
    year, gross = _year(year), _amount(allocated_usd)
    expenses = _amount(allocated_expenses_usd)
    country = country.upper()
    if country == "UK":
        country = "GB"
    treaties = {
        "GB": (20000, "https://www.gov.uk/government/publications/usa-tax-treaties/2001-uk-usa-double-taxation-convention-as-amended-by-the-2002-protocol-in-force"),
        "FR": (10000, "https://www.irs.gov/pub/irs-trty/francetech.pdf"),
        "MX": (3000, "https://www.irs.gov/pub/irs-trty/mexico.pdf"),
    }
    assumptions = [
        "Short US-team employee visit; host wage allocation supplied as a modeled input",
        "No endorsements, performance bonuses or other host-country income",
        "No extra host social insurance assumed; actual coverage/secondment documents may differ",
        "FX snapshot 2026-10-08 is not the unknown tax-year average",
        "Treaty thresholds include reimbursements; zero expense input is an assumption",
    ]
    out = {"country": country, "currency": "USD", "year": year,
           "allocated_income": gross, "assumptions": assumptions,
           "tax": 0.0, "foreign_income_tax": 0.0,
           "fx_date": "2026-10-08", "sources": [SOURCES["fx"]]}
    if country == "CA":
        if not us_treaty_resident:
            raise ValueError("Canadian non-treaty visiting scenario requires separate residency analysis")
        out.update({"method": "conditional_US_Canada_XVI3_XV2b_exemption",
                    "sources": [SOURCES["us_ca_treaty"]]})
        assumptions.append("US treaty resident, US payer, <=183 days in any relevant 12 months, no Canadian PE bearing wages")
        return out
    if country not in treaties:
        raise ValueError("Supported host countries are CA, GB/UK, FR and MX")
    threshold, treaty_url = treaties[country]
    out["sources"].append(treaty_url)
    out["treaty_threshold_usd"] = threshold
    if us_treaty_resident and gross + expenses <= threshold:
        out["method"] = "conditional_US_treaty_athlete_threshold_and_employment_exemption"
        assumptions.append("Foreign payer, no host PE bearing remuneration and short stay; treaty benefits assumed")
        return out
    if country == "MX":
        tax = gross * .25
        out.update({"method": "nonresident_sportsperson_25pct_gross_option",
                    "rate": .25, "rules_year": 2026, "proxy": year != 2026})
        out["sources"].append("https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf#page=209")
        assumptions.append("Domestic gross-income option in LISR Article170; no net-income election")
    elif country == "GB":
        usd_gbp = 1.4240 / 1.8822
        pounds = gross * usd_gbp
        allowance = max(0, 12570 - .5 * max(0, pounds - 100000)) if uk_personal_allowance else 0.0
        tax_gbp, bands = progressive(max(0, pounds - allowance),
                                      [(37700, .20), (125140, .40), (None, .45)])
        tax = tax_gbp / usd_gbp
        out.update({"method": "England_nonresident_progressive_income_tax",
                    "rules_year": "2026-27", "proxy": year == 2027,
                    "fx_gbp_per_usd": usd_gbp, "gross_gbp": pounds,
                    "personal_allowance_gbp": allowance, "brackets_gbp": bands,
                    "tax_gbp": tax_gbp})
        out["sources"].extend([
            "https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past",
            "https://www.gov.uk/tax-uk-income-live-abroad/personal-allowance",
            "https://www.gov.uk/guidance/pay-tax-in-the-uk-as-a-foreign-performer"])
        assumptions.append("UK allowance not assumed from US residence alone; UK/EEA nationality or other entitlement may change it")
    else:
        usd_eur = 1.4240 / 1.5950
        euros = gross * usd_eur
        deduction = min(euros, max(509.0, min(.1 * euros, 14555.0))) if euros else 0.0
        taxable = max(0, euros - deduction)
        regular, bands = progressive(taxable, [(11600, 0), (29579, .11),
                                               (84577, .30), (181917, .41), (None, .45)])
        minimum = .20 * min(taxable, 29579) + .30 * max(0, taxable - 29579)
        income_tax = max(regular, minimum)
        high_income = .03 * max(0, min(taxable, 500000) - 250000) + .04 * max(0, taxable - 500000)
        tax = (income_tax + high_income) / usd_eur
        out.update({"method": "France_nonresident_progressive_minimum_plus_CEHR_proxy",
                    "rules_year": "2025_income_2026_assessment", "proxy": True,
                    "fx_eur_per_usd": usd_eur, "gross_eur": euros,
                    "professional_expense_deduction_eur": deduction,
                    "taxable_income_eur": taxable, "regular_tax_eur": regular,
                    "nonresident_minimum_eur": minimum, "brackets_eur": bands,
                    "CEHR_eur": high_income, "tax_eur": income_tax + high_income,
                    "indicative_withholding_not_extra_tax_usd": gross * .15})
        out["sources"].extend([
            "https://www.impots.gouv.fr/particulier/le-calcul-de-votre-impot",
            "https://bofip.impots.gouv.fr/bofip/2491-PGP.html/identifiant=BOI-IR-LIQ-20-10-20260407",
            "https://bofip.impots.gouv.fr/bofip/10855-PGP.html/identifiant=BOI-BAREME-000035-20260217",
            "https://bofip.impots.gouv.fr/bofip/7804-PGP.html/identifiant=BOI-IR-CHR-20170711"])
        assumptions.extend([
            "One tax share, salary expense deduction10% subject to minimum509EUR and cap14555EUR; no extra deductions",
            "Latest verified assessment bands for2025 income used as explicit2026/2027 proxy",
            "French-source wage-only RFR proxy for CEHR, no exceptional-income smoothing; no resident-only CDHR",
            "French athlete15% withholding is non-final and is NOT added to modeled final liability",
        ])
    out["tax"] = out["foreign_income_tax"] = tax
    return out


if __name__ == "__main__":
    import json
    print(json.dumps({"us_1m": calculate_us(1000000),
                      "ontario_1m_usd": calculate_canada(1000000)}, indent=2))
