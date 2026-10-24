"""Build the synthetic fixtures (SPEC §10). All names, labels and values are fictional.

    py tools\\build_fixtures.py [--out <dir>]      (default: <repo>/fixtures)

Writes per catalogue fixture: source.xlsx (fictional source workbook) + spec.json (catalogue spec that parses it),
and EXPO_SYN (synthetic Merit-shaped dim_life + run_manifest + mapping tables). SUB_X / SUB_Y are built by
tools/build_submissions.py through the template generator (T). Deterministic: re-running reproduces identical bytes.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

from pw.io_excel import new_workbook  # noqa: E402

SEED = 20261024


def _dump(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


class Sheet:
    """Small grid writer: merged group headers, header rows, label columns, numeric/text data."""

    def __init__(self, wb, name):
        self.wb = wb
        self.ws = wb.add_worksheet(name)
        self.hdr = wb.add_format({"bold": True, "align": "center", "border": 1})
        self.lab = wb.add_format({"bold": True, "border": 1})
        self.num = wb.add_format({"num_format": "#,##0.00", "border": 1})
        self.fac = wb.add_format({"num_format": "0.0000", "border": 1})
        self.txt = wb.add_format({"border": 1, "align": "center"})

    def title(self, r, c, text):
        self.ws.write(r, c, text, self.wb.add_format({"bold": True, "font_size": 12}))

    def grid(self, r0, c0, header_rows, row_labels, data, group_rows=(), fmt=None):
        """header_rows: list of lists (len = n data cols); group_rows: indexes of header rows to merge across runs.
        row_labels: list of lists (one list per data row). Coordinates are 0-based (xlsxwriter)."""
        nlab = len(row_labels[0]) if row_labels else 0
        for i, hr in enumerate(header_rows):
            if i in group_rows:
                j = 0
                while j < len(hr):
                    k = j
                    while k + 1 < len(hr) and hr[k + 1] == hr[j]:
                        k += 1
                    if k > j:
                        self.ws.merge_range(r0 + i, c0 + nlab + j, r0 + i, c0 + nlab + k, hr[j], self.hdr)
                    else:
                        self.ws.write(r0 + i, c0 + nlab + j, hr[j], self.hdr)
                    j = k + 1
            else:
                for j, v in enumerate(hr):
                    self.ws.write(r0 + i, c0 + nlab + j, v, self.hdr)
        base_r = r0 + len(header_rows)
        for i, labs in enumerate(row_labels):
            for j, v in enumerate(labs):
                self.ws.write(base_r + i, c0 + j, v, self.lab)
            for j, v in enumerate(data[i]):
                if isinstance(v, str):
                    self.ws.write_string(base_r + i, c0 + nlab + j, v, self.txt)
                else:
                    self.ws.write_number(base_r + i, c0 + nlab + j, v, fmt or self.num)
        self.ws.set_column(c0, c0 + nlab - 1, 14)
        return base_r


def xl(r, c):
    """0-based -> A1"""
    from openpyxl.utils import get_column_letter
    return f"{get_column_letter(c + 1)}{r + 1}"


GENDER_MAP = {"Male": "M", "Female": "F"}


def bands(edges, top):
    labs = [f"{a}-{b - 1}" for a, b in zip(edges, edges[1:])] + [f"{edges[-1]}+"]
    rng = [[a, b - 1] for a, b in zip(edges, edges[1:])] + [[edges[-1], top]]
    return labs, rng


def age_factor(lo, hi):
    mid = (lo + min(hi, 85)) / 2
    return round(0.55 + 0.012 * mid + 0.00045 * mid * mid, 4)


# =============================================================================================== CAT_ALPHA
def build_alpha(out: Path):
    d = out / "CAT_ALPHA"
    d.mkdir(parents=True, exist_ok=True)
    edges = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
    labs, rng = bands(edges, 120)                       # 15 bands
    plans = [f"P{i}" for i in range(1, 8)]
    plan_labels = {p: f"Plan {p[1:]}" for p in plans}
    tier = {"P1": 1.60, "P2": 1.35, "P3": 1.18, "P4": 1.00, "P5": 0.86, "P6": 0.74, "P7": 0.63}
    nets = {"P1": "N_PLAT", "P2": "N_GOLD", "P3": "N_SILV", "P4": "N_BRNZ", "P5": "N_STD", "P6": "N_CLIN", "P7": "N_BASIC"}
    tpas = ["TPA_RED", "TPA_BLUE", "TPA_GREEN"]
    wb = new_workbook(d / "source.xlsx", title="CAT_ALPHA fictional catalogue")
    sh = Sheet(wb, "Base Rates")
    sh.title(0, 0, "Fictional catalogue ALPHA - individual base rates (AED, net), unified principal/dependant")
    hdr1, hdr2 = [], []
    for p in plans:
        hdr1 += [plan_labels[p]] * 2
        hdr2 += ["Male", "Female"]
    data = []
    for (lo, hi) in rng:
        row = []
        for p in plans:
            for g in ("M", "F"):
                if lo >= 70 and p in ("P6", "P7"):
                    row.append("Refer")
                    continue
                fem = 1.07 if (g == "F" and 18 <= lo <= 44) else (0.97 if g == "F" else 1.0)
                row.append(round(1180.0 * tier[p] * age_factor(lo, hi) * fem, 2))
        data.append(row)
    sh.grid(2, 0, [hdr1, hdr2], [[l] for l in labs], data, group_rows=(0,))
    base_anchor = xl(2, 0)

    # 2-D AML factor by network (reference per network: SPEC §3.4)
    sf = Sheet(wb, "Factors")
    sf.title(0, 0, "AML factor by network (fictional)")
    aml_opts = ["300000", "750000", "1250000", "2000000"]
    net_cols = ["N_PLAT", "N_GOLD", "N_SILV", "N_BRNZ", "N_STD", "N_CLIN", "N_BASIC"]
    ref_by_net = {"N_PLAT": "2000000", "N_GOLD": "1250000", "N_SILV": "1250000", "N_BRNZ": "750000",
                  "N_STD": "750000", "N_CLIN": "750000", "N_BASIC": "300000"}
    steps = {"300000": -3, "750000": -2, "1250000": -1, "2000000": 0}
    order = ["300000", "750000", "1250000", "2000000"]
    aml = []
    for a in aml_opts:
        row = []
        for n in net_cols:
            k = order.index(a) - order.index(ref_by_net[n])
            row.append(round(1.0 + 0.031 * k + (0.002 * k * k if k < 0 else 0.0), 4))
        aml.append(row)
    sf.grid(2, 0, [net_cols], [[a] for a in aml_opts], aml, fmt=sf.fac)
    aml_anchor = xl(2, 0)

    sa = Sheet(wb, "Add-ons")
    sa.title(0, 0, "Maternity module, AED per eligible female (fictional)")
    mat_opts = ["M10", "M20", "MAML"]
    mat = [[round(1450 + 140 * (6 - i) + 380 * j, 2) for i, _ in enumerate(net_cols)] for j, _ in enumerate(mat_opts)]
    sa.grid(2, 0, [net_cols], [[m] for m in mat_opts], mat)
    mat_anchor = xl(2, 0)
    wb.close()

    spec = {
        "spec_id": "CAT_ALPHA_SPEC", "spec_version": "1",
        "catalogue": {"catalogue_id": "CAT_ALPHA", "owner": "FICTIONAL_CEDANT_A", "kind": "EXPIRING", "version": "1",
                      "effective_date": "2026-01-01", "currency": "AED", "premium_basis": "NET"},
        "source_file": "source.xlsx",
        "maps": {"gender": GENDER_MAP, "net_codes": {n: n for n in net_cols}, "aml_opts": {a: a for a in aml_opts},
                 "mat_opts": {m: m for m in mat_opts}},
        "band_maps": {"alpha15": {"parse": labs}},
        "text_values": {"Refer": "REFER"},
        "scopes": [{
            "scope_id": "ALPHA_IND_A", "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A",
            "tpa_set": tpas,
            "plans": [{"plan_id": p, "label": plan_labels[p], "tier_rank": i + 1,
                       "network_by_tpa": {t: nets[p] for t in tpas},
                       "attributes": {"clinic_restricted": p in ("P6", "P7"), "gp_referral": p == "P7",
                                      "split_ip_op": p in ("P2", "P3")},
                       "defaults": {"copay_op_diag": "10%", "ded_consult": "D30", "copay_pharmacy": "0%",
                                    "aml": ref_by_net[nets[p]], "network_option": "OPT1", "module_maternity": "M10"}}
                      for i, p in enumerate(plans)],
            "components": [
                {"component_id": "base", "type": "BASE_TABLE",
                 "sources": [{"sheet": "Base Rates", "anchor": base_anchor,
                              "row_dims": [{"dim": "age", "band_map": "alpha15"}],
                              "col_dims": [{"dim": "plan", "map": "@plans"}, {"dim": "gender", "map": "gender"}],
                              "n_rows": len(labs), "n_cols": 2 * len(plans)}]},
                {"component_id": "f_opdiag", "type": "FACTOR_TABLE", "family": "copay_op_diag", "reference_level": "0%",
                 "values": {"0%": 1.0, "10%": 0.955, "20%": 0.915, "AED25": 0.988}},
                {"component_id": "f_consult", "type": "FACTOR_TABLE", "family": "ded_consult", "reference_level": "D30",
                 "values": {"NIL": 1.064, "D30": 1.0, "D60": 0.972, "P15_C40": 0.991}},
                {"component_id": "f_pharm", "type": "FACTOR_TABLE", "family": "copay_pharmacy", "reference_level": "0%",
                 "values": {"0%": 1.0, "15%": 0.972, "25%": 0.951}},
                {"component_id": "f_aml", "type": "FACTOR_TABLE", "family": "aml", "keys": ["aml", "network"],
                 "reference_level_by": "network", "reference_level_by_key": ref_by_net,
                 "sources": [{"sheet": "Factors", "anchor": aml_anchor,
                              "row_dims": [{"dim": "aml", "map": "aml_opts"}],
                              "col_dims": [{"dim": "network", "map": "net_codes"}],
                              "n_rows": len(aml_opts), "n_cols": len(net_cols)}]},
                {"component_id": "f_netopt", "type": "FACTOR_TABLE", "family": "network_option", "reference_level": "OPT1",
                 "keys": ["plan", "network_option"],
                 "rows": [{"key": {"plan": "ANY", "network_option": "OPT1"}, "value": 1.0},
                          {"key": {"plan": "P2", "network_option": "OPT2"}, "value": 0.88},
                          {"key": {"plan": "P3", "network_option": "OPT2"}, "value": 0.905}]},
                {"component_id": "f_tpa", "type": "FACTOR_TABLE", "family": "tpa", "keys": ["tpa"], "reference_level": "TPA_RED",
                 "values": {"TPA_RED": 1.0, "TPA_BLUE": 1.0, "TPA_GREEN": 0.93}},
                {"component_id": "f_nat", "type": "FACTOR_TABLE", "family": "nationality", "keys": ["nationality_group"],
                 "reference_level": "OTHER", "values": {"GRP_SOUTH": 0.915, "GRP_EAST": 0.94, "GRP_WEST": 1.12, "OTHER": 1.0}},
                {"component_id": "m_mat", "type": "MODULE", "family": "module_maternity", "unit": "PER_ELIGIBLE_FEMALE",
                 "keys": ["network", "module_maternity"],
                 "sources": [{"sheet": "Add-ons", "anchor": mat_anchor,
                              "row_dims": [{"dim": "module_maternity", "map": "mat_opts"}],
                              "col_dims": [{"dim": "network", "map": "net_codes"}],
                              "n_rows": len(mat_opts), "n_cols": len(net_cols)}]},
                {"component_id": "loading", "type": "LOADING", "cap": 0.30}
            ],
            "formula": {"order": ["BASE", "FACTORS", "MODULES"], "rounding": 2},
            "benefits": {
                "P1": [{"benefit_code": "aml", "value": 2000000, "condition_text": "AED 2m per member per year"},
                       {"benefit_code": "room_type", "value": "PRIVATE"},
                       {"benefit_code": "op_diag_copay", "structure": {"type": "PCT", "pct": 0.10}, "value": 0.10,
                        "condition_text": "10% co-pay (catalogue default)"}],
                "P7": [{"benefit_code": "aml", "value": 300000},
                       {"benefit_code": "room_type", "value": "SEMI_PRIVATE"},
                       {"benefit_code": "gp_referral", "value": True},
                       {"benefit_code": "alt_medicine_limit", "value": None, "condition_text": "as per regulator list"}]}
        }],
        "rules": [
            {"rule_id": "A_R1", "scope": {"product_type": "INDIVIDUAL"}, "type": "REFERRAL",
             "parameters": {"claim_amount_gt": 20000}, "text": "Claims above AED 20k referred to the lead reinsurer"},
            {"rule_id": "A_R2", "scope": {"tpa": "TPA_GREEN"}, "type": "LOADING_CAP", "parameters": {"max_loading": 0.30},
             "text": "Maximum loading 30%"},
            {"rule_id": "A_R3", "scope": {}, "type": "REVIEW", "parameters": {"frequency": "QUARTERLY"},
             "text": "Rates reviewed quarterly"}]
    }
    _dump(spec, d / "spec.json")
    return spec


# =============================================================================================== CAT_BETA
BETA_PLANTED = [  # (section, level, band, plan, gm) -> multiplier applied instead of the flat one
    ("PRINCIPAL", "20%", "61+", "P2", "Female Married", 1.137),
    ("PRINCIPAL", "20%", "61+", "P5", "Male Single", 1.211),
    ("DEPENDANT", "20%", "0-17", "P5", "Female Single", 0.992),
    ("DEPENDANT", "20%", "31-35", "P6", "Male Married", 1.304),
    ("DEPENDANT", "20%", "18-25", "P6", "Female Married", 1.048),
]


def build_beta(out: Path):
    d = out / "CAT_BETA"
    d.mkdir(parents=True, exist_ok=True)
    edges = [0, 18, 26, 31, 36, 41, 51, 61]
    labs, rng = bands(edges, 120)                    # 8 bands
    plans = [f"P{i}" for i in range(1, 7)]
    plan_labels = {p: f"Tier {p[1:]}" for p in plans}
    tier = {"P1": 1.55, "P2": 1.30, "P3": 1.12, "P4": 0.98, "P5": 0.84, "P6": 0.72}
    gm_labels = ["Male Single", "Male Married", "Female Single", "Female Married"]
    gm_map = {"Male Single": {"gender": "M", "marital": "SINGLE"}, "Male Married": {"gender": "M", "marital": "MARRIED"},
              "Female Single": {"gender": "F", "marital": "SINGLE"}, "Female Married": {"gender": "F", "marital": "MARRIED"}}
    gm_fac = {"Male Single": 1.0, "Male Married": 1.03, "Female Single": 1.05, "Female Married": 1.21}
    levels = [("NIL", "Nil co-pay", 1.0), ("10%", "10% co-pay", 0.952), ("20%", "20% co-pay", 0.916)]
    sec_fac = {"PRINCIPAL": 1.0, "DEPENDANT": 0.91}
    wb = new_workbook(d / "source.xlsx", title="CAT_BETA fictional catalogue")
    sh = Sheet(wb, "Rates")
    sh.title(0, 0, "Fictional catalogue BETA - co-pay blocks side by side (AED, net)")
    ncol = len(plans) * len(gm_labels)
    expected = []
    sources = {lv: [] for lv, _, _ in levels}
    r = 2
    for sec in ("PRINCIPAL", "DEPENDANT"):
        sh.title(r, 0, f"Section: {sec.title()}")
        r += 1
        for bi, (lv, lvlab, mult) in enumerate(levels):
            c0 = bi * (ncol + 2)
            hdr0 = [lvlab] * ncol
            hdr1, hdr2 = [], []
            for p in plans:
                hdr1 += [plan_labels[p]] * len(gm_labels)
                hdr2 += gm_labels
            data = []
            for bl, (lo, hi) in zip(labs, rng):
                row = []
                for p in plans:
                    for gm in gm_labels:
                        nil = round(1050.0 * tier[p] * age_factor(lo, hi) * gm_fac[gm] * sec_fac[sec], 2)
                        v = round(nil * mult, 2)
                        for (ps, pl, pb, pp, pg, bad) in BETA_PLANTED:
                            if (ps, pl, pb, pp, pg) == (sec, lv, bl, p, gm):
                                v = round(nil * bad, 2)
                                expected.append({"section": sec, "level": lv, "band": bl, "plan": p, "column": gm,
                                                 "source_value": v, "expected_value": round(nil * mult, 2),
                                                 "nil_value": nil})
                        row.append(v)
                data.append(row)
            # write block label row (decoration), then the grid (plan / gm headers)
            sh.grid(r, c0, [hdr0, hdr1, hdr2], [[l] for l in labs], data, group_rows=(0, 1))
            sources[lv].append({"sheet": "Rates", "anchor": xl(r + 1, c0),
                                "row_dims": [{"dim": "age", "band_map": "beta8"}],
                                "col_dims": [{"dim": "plan", "map": "@plans"}, {"dims": ["gender", "marital"], "map": "gm"}],
                                "n_rows": len(labs), "n_cols": ncol, "fixed": {"member_category": sec}})
        r += 3 + len(labs) + 2
    wb.close()
    _dump({"planted": expected, "multipliers": {"10%": 0.952, "20%": 0.916}}, d / "expected_v2.json")
    spec = {
        "spec_id": "CAT_BETA_SPEC", "spec_version": "1",
        "catalogue": {"catalogue_id": "CAT_BETA", "owner": "FICTIONAL_CEDANT_B", "kind": "EXPIRING", "version": "1",
                      "effective_date": "2026-01-01", "currency": "AED", "premium_basis": "NET"},
        "source_file": "source.xlsx",
        "maps": {"gm": gm_map},
        "band_maps": {"beta8": {"parse": labs}},
        "scopes": [{
            "scope_id": "BETA_IND_A", "product_type": "INDIVIDUAL", "regulator": "DOH", "rating_region": "RGN_A",
            "tpa_set": ["TPA_RED", "TPA_BLUE"],
            "plans": [{"plan_id": p, "label": plan_labels[p], "tier_rank": i + 1,
                       "network_by_tpa": {"TPA_RED": f"B_NET{i + 1}", "TPA_BLUE": f"B_NET{i + 1}"},
                       "defaults": {"copay_op_diag": "NIL"}} for i, p in enumerate(plans)],
            "components": [
                {"component_id": "blocks", "type": "BLOCK_SET", "family": "copay_op_diag", "reference_level": "NIL",
                 "tolerance_abs": 0.01, "resolution": "DERIVED", "multiplier_decimals": 4,
                 "blocks": [{"level": lv, "sources": sources[lv]} for lv, _, _ in levels]}
            ],
            "formula": {"rounding": 2}
        }],
        "rules": [{"rule_id": "B_R1", "scope": {}, "type": "UW", "parameters": {"medical_declaration": "ALL_MEMBERS"},
                   "text": "Declaration form for all members"}]
    }
    _dump(spec, d / "spec.json")
    return spec


# =============================================================================================== CAT_GAMMA
def build_gamma(out: Path):
    d = out / "CAT_GAMMA"
    d.mkdir(parents=True, exist_ok=True)
    edges = [0, 18, 30, 40, 50, 55, 60, 65]
    labs, rng = bands(edges, 120)
    plans = ["G1", "G2", "G3", "G4"]
    plan_labels = {p: f"Option {p[1]}" for p in plans}
    tier = {"G1": 1.40, "G2": 1.12, "G3": 0.95, "G4": 0.80}
    wb = new_workbook(d / "source.xlsx", title="CAT_GAMMA fictional catalogue")
    sh = Sheet(wb, "SME Base")
    sh.title(0, 0, "Fictional catalogue GAMMA - SME base rates (AED, net)")
    hdr1, hdr2 = [], []
    for p in plans:
        hdr1 += [plan_labels[p]] * 2
        hdr2 += ["Male", "Female"]
    data = [[round(860.0 * tier[p] * age_factor(lo, hi) * (1.06 if g == "Female" else 1.0), 2)
             for p in plans for g in ("Male", "Female")] for lo, hi in rng]
    sh.grid(2, 0, [hdr1, hdr2], [[l] for l in labs], data, group_rows=(0,))
    base_anchor = xl(2, 0)
    sa = Sheet(wb, "Add-ons")
    dent = ["D1500", "D3000", "D6000"]
    opt = ["O400", "O900"]
    mat = ["M12", "M24"]
    sa.title(0, 0, "Dental (AED per member)")
    sa.grid(1, 0, [[plan_labels[p] for p in plans]], [[x] for x in dent],
            [[round((210 + 95 * i) * (1.5 - 0.17 * j), 2) for j, _ in enumerate(plans)] for i, _ in enumerate(dent)])
    sa.title(7, 0, "Optical (AED per member)")
    sa.grid(8, 0, [[plan_labels[p] for p in plans]], [[x] for x in opt],
            [[round((55 + 70 * i) * (1.4 - 0.15 * j), 2) for j, _ in enumerate(plans)] for i, _ in enumerate(opt)])
    sa.title(13, 0, "Maternity (AED per eligible female)")
    sa.grid(14, 0, [[plan_labels[p] for p in plans]], [[x] for x in mat],
            [[round((1600 + 900 * i) * (1.3 - 0.1 * j), 2) for j, _ in enumerate(plans)] for i, _ in enumerate(mat)])
    wb.close()
    ident = lambda xs: {x: x for x in xs}  # noqa: E731

    def mod(cid, fam, unit, anchor, opts):
        return {"component_id": cid, "type": "MODULE", "family": fam, "unit": unit, "keys": ["plan", fam],
                "default_option": "NONE",
                "sources": [{"sheet": "Add-ons", "anchor": anchor, "row_dims": [{"dim": fam, "map": fam}],
                             "col_dims": [{"dim": "plan", "map": "@plans"}], "n_rows": len(opts), "n_cols": len(plans)}]}
    spec = {
        "spec_id": "CAT_GAMMA_SPEC", "spec_version": "1",
        "catalogue": {"catalogue_id": "CAT_GAMMA", "owner": "FICTIONAL_CEDANT_C", "kind": "MARKET", "version": "1",
                      "effective_date": "2026-01-01", "currency": "AED", "premium_basis": "NET"},
        "source_file": "source.xlsx",
        "maps": {"gender": GENDER_MAP, "module_dental": ident(dent), "module_optical": ident(opt), "module_maternity": ident(mat)},
        "band_maps": {"gamma8": {"parse": labs}},
        "scopes": [{
            "scope_id": "GAMMA_SME_B", "product_type": "SME", "regulator": "DHA", "rating_region": "RGN_B",
            "tpa_set": ["TPA_RED", "TPA_BLUE"],
            "plans": [{"plan_id": p, "label": plan_labels[p], "tier_rank": i + 1,
                       "network_by_tpa": {"TPA_RED": f"G_NET{i + 1}", "TPA_BLUE": f"G_NET{i + 1}"}}
                      for i, p in enumerate(plans)],
            "components": [
                {"component_id": "base", "type": "BASE_TABLE",
                 "sources": [{"sheet": "SME Base", "anchor": base_anchor, "row_dims": [{"dim": "age", "band_map": "gamma8"}],
                              "col_dims": [{"dim": "plan", "map": "@plans"}, {"dim": "gender", "map": "gender"}],
                              "n_rows": len(labs), "n_cols": 2 * len(plans)}]},
                {"component_id": "f_size", "type": "FACTOR_TABLE", "family": "group_size", "keys": ["group_size_band"],
                 "reference_level": "10-49",
                 "rows": [{"key": {"group_size_band": [3, 9]}, "value": 1.085, "labels": {"group_size_band": "3-9"}},
                          {"key": {"group_size_band": [10, 49]}, "value": 1.0, "labels": {"group_size_band": "10-49"}},
                          {"key": {"group_size_band": [50, 200]}, "value": 0.962, "labels": {"group_size_band": "50-200"}}]},
                mod("m_dental", "module_dental", "PER_MEMBER", "A2", dent),
                mod("m_optical", "module_optical", "PER_MEMBER", "A9", opt),
                mod("m_mat", "module_maternity", "PER_ELIGIBLE_FEMALE", "A15", mat),
                {"component_id": "loading", "type": "LOADING", "cap": 0.25}
            ],
            "formula": {"rounding": 2}
        }],
        "rules": [{"rule_id": "G_R1", "scope": {"product_type": "SME"}, "type": "ELIGIBILITY",
                   "parameters": {"group_size_min": 3, "group_size_max": 200}, "text": "Group size 3 to 200"},
                  {"rule_id": "G_R2", "scope": {"product_type": "SME"}, "type": "RENEWAL",
                   "parameters": {"nlr_auto_renew_max": 0.70}, "text": "NLR up to 70% renews automatically; above is referred"}]
    }
    _dump(spec, d / "spec.json")
    return spec


# =============================================================================================== CAT_DELTA
def build_delta(out: Path):
    d = out / "CAT_DELTA"
    d.mkdir(parents=True, exist_ok=True)
    cats = [("Worker", "EMPLOYEE", [("18-44", 640.0), ("45-64", 1210.0), ("65+", "Refer")]),
            ("Self Sponsor", "SMALL_INVESTOR", [("18-44", 1580.0), ("45-64", 2290.0), ("65+", "Refer")]),
            ("Family Member", "DEPENDANT", [("0-17", 720.0), ("18-44", 980.0), ("45-64", 2540.0), ("65+", "Refer")]),
            ("Household Staff", "DOMESTIC", [("18-44", 560.0), ("45-64", 1130.0)])]
    wb = new_workbook(d / "source.xlsx", title="CAT_DELTA fictional catalogue")
    sh = Sheet(wb, "Basic")
    sh.title(0, 0, "Fictional catalogue DELTA - basic plan, gross premium (AED)")
    rows, data = [], []
    for lab, _, bl in cats:
        for b, v in bl:
            rows.append([lab, b])
            data.append([v])
    sh.grid(2, 0, [["Gross premium"]], rows, data)
    wb.close()
    all_bands = sorted({b for _, _, bl in cats for b, _ in bl}, key=lambda s: int(s.split("-")[0].rstrip("+")))
    spec = {
        "spec_id": "CAT_DELTA_SPEC", "spec_version": "1",
        "catalogue": {"catalogue_id": "CAT_DELTA", "owner": "FICTIONAL_CEDANT_D", "kind": "EXPIRING", "version": "1",
                      "effective_date": "2026-01-01", "currency": "AED", "premium_basis": "GROSS"},
        "source_file": "source.xlsx",
        "maps": {"cat": {lab: mc for lab, mc, _ in cats}},
        "band_maps": {"delta": {"parse": all_bands}},
        "text_values": {"Refer": "REFER"},
        "scopes": [{
            "scope_id": "DELTA_BASIC_C", "product_type": "BASIC", "regulator": "DOH", "rating_region": "RGN_C",
            "tpa_set": ["DIRECT"],
            "plans": [{"plan_id": "BASIC", "label": "Basic", "tier_rank": 1, "network_by_tpa": {"DIRECT": "D_NET"}}],
            "components": [
                {"component_id": "base", "type": "BASE_TABLE",
                 "sources": [{"sheet": "Basic", "anchor": "A3",
                              "row_dims": [{"dim": "member_category", "map": "cat"}, {"dim": "age", "band_map": "delta"}],
                              "col_dims": [{"dim": "premium_column", "labels": {"Gross premium": {}}}],
                              "n_rows": len(rows), "n_cols": 1, "fixed": {"plan": "BASIC"}}]},
                {"component_id": "policy_fee", "type": "FEE", "amount": 18.0, "premium_basis": "GROSS"},
                {"component_id": "loading", "type": "LOADING", "cap": 0.22}
            ],
            "formula": {"rounding": 2, "min_premium": 400.0}
        }],
        "rules": [{"rule_id": "D_R1", "scope": {"product_type": "BASIC"}, "type": "ELIGIBILITY",
                   "parameters": {"salary_max": 4500, "group_lives_min": 120, "group_lives_max": 450},
                   "text": "Salary up to AED 4.5k; groups of 120-450 lives"},
                  {"rule_id": "D_R2", "scope": {}, "type": "REFERRAL", "parameters": {"age_gt": 64},
                   "text": "Above 64: refer to the lead reinsurer"}]
    }
    _dump(spec, d / "spec.json")
    return spec


# =============================================================================================== CAT_RETIREE
def build_retiree(out: Path):
    d = out / "CAT_RETIREE"
    d.mkdir(parents=True, exist_ok=True)
    ages = list(range(55, 100))
    plans = ["R1", "R2"]
    wb = new_workbook(d / "source.xlsx", title="CAT_RETIREE fictional catalogue")
    sh = Sheet(wb, "Retiree")
    sh.title(0, 0, "Fictional catalogue RETIREE - annual premium by ENTRY age (AED, net)")
    hdr1, hdr2 = [], []
    for p in plans:
        hdr1 += [f"Retiree {p[1]}"] * 2
        hdr2 += ["Male", "Female"]
    data = [[round(3900.0 * (1.0 if p == "R1" else 0.78) * (1.045 ** (a - 55)) * (0.94 if g == "Female" else 1.0), 2)
             for p in plans for g in ("Male", "Female")] for a in ages]
    sh.grid(2, 0, [hdr1, hdr2], [[a] for a in ages], data, group_rows=(0,))
    wb.close()
    spec = {
        "spec_id": "CAT_RETIREE_SPEC", "spec_version": "1",
        "catalogue": {"catalogue_id": "CAT_RETIREE", "owner": "FICTIONAL_CEDANT_E", "kind": "MARKET", "version": "1",
                      "effective_date": "2026-01-01", "currency": "AED", "premium_basis": "NET"},
        "source_file": "source.xlsx",
        "maps": {"gender": GENDER_MAP},
        "band_maps": {"single": {"parse": [str(a) for a in ages]}},
        "scopes": [{
            "scope_id": "RET_A", "product_type": "RETIREE", "regulator": "DHA", "rating_region": "RGN_A",
            "tpa_set": ["TPA_RED"], "rating_basis_age": "ENTRY_AGE",
            "plans": [{"plan_id": p, "label": f"Retiree {p[1]}", "tier_rank": i + 1, "network_by_tpa": {"TPA_RED": "R_NET"},
                       "defaults": {"payment_frequency": "ANNUAL"}} for i, p in enumerate(plans)],
            "components": [
                {"component_id": "base", "type": "BASE_TABLE",
                 "sources": [{"sheet": "Retiree", "anchor": "A3", "row_dims": [{"dim": "age", "band_map": "single"}],
                              "col_dims": [{"dim": "plan", "map": "@plans"}, {"dim": "gender", "map": "gender"}],
                              "n_rows": len(ages), "n_cols": 4}]},
                {"component_id": "max_entry", "type": "REFER", "rows": [{"key": {"age": [76, 120]}}],
                 "notes": "entry age above 75 is referred (rule RT_R1)"},
                {"component_id": "f_freq", "type": "FACTOR_TABLE", "family": "payment_frequency", "reference_level": "ANNUAL",
                 "values": {"ANNUAL": 1.0, "SEMI": 1.018, "QUARTERLY": 1.027, "MONTHLY": 1.041}}
            ],
            "formula": {"rounding": 2}
        }],
        "rules": [{"rule_id": "RT_R1", "scope": {"product_type": "RETIREE"}, "type": "ELIGIBILITY",
                   "parameters": {"max_entry_age": 75}, "text": "Maximum entry age 75"}]
    }
    _dump(spec, d / "spec.json")
    return spec


# =============================================================================================== CAT_IPMI
def build_ipmi(out: Path):
    d = out / "CAT_IPMI"
    d.mkdir(parents=True, exist_ok=True)
    edges = list(range(0, 81, 5))
    labs, rng = bands(edges, 120)        # 0-4 ... 75-79, 80+
    plans = ["CORE", "PLUS"]
    wb = new_workbook(d / "source.xlsx", title="CAT_IPMI fictional catalogue")
    sh = Sheet(wb, "IPMI Base")
    sh.title(0, 0, "Fictional catalogue IPMI - base premium (USD), worldwide excluding USA, nil deductible")
    hdr1, hdr2 = [], []
    for p in plans:
        hdr1 += [p.title()] * 2
        hdr2 += ["Male", "Female"]
    data = [[round(1450.0 * (1.0 if p == "CORE" else 1.38) * age_factor(lo, hi) * (1.04 if g == "Female" else 1.0), 2)
             for p in plans for g in ("Male", "Female")] for lo, hi in rng]
    sh.grid(2, 0, [hdr1, hdr2], [[l] for l in labs], data, group_rows=(0,))
    sf = Sheet(wb, "Deductibles")
    areas = ["WW_INC_USA", "WW_EXC_USA", "REGIONAL"]
    deds = ["D0", "D500", "D1500", "D5000"]
    sf.title(0, 0, "Deductible factor by area of cover")
    sf.grid(1, 0, [areas], [[x] for x in deds],
            [[round(1.0 - (0.06 + 0.012 * j) * i, 4) for j, _ in enumerate(areas)] for i, _ in enumerate(deds)], fmt=sf.fac)
    wb.close()
    ident = lambda xs: {x: x for x in xs}  # noqa: E731
    spec = {
        "spec_id": "CAT_IPMI_SPEC", "spec_version": "1",
        "catalogue": {"catalogue_id": "CAT_IPMI", "owner": "FICTIONAL_CARRIER_F", "kind": "MARKET", "version": "1",
                      "effective_date": "2026-01-01", "currency": "USD", "premium_basis": "NET"},
        "source_file": "source.xlsx",
        "maps": {"gender": GENDER_MAP, "areas": ident(areas), "deds": ident(deds), "plans": {"Core": "CORE", "Plus": "PLUS"}},
        "band_maps": {"ipmi5": {"parse": labs}},
        "scopes": [{
            "scope_id": "IPMI_GLOBAL", "product_type": "IPMI", "regulator": "NONE", "rating_region": "IPMI_GLOBAL",
            "tpa_set": ["TPA_INTL"],
            "plans": [{"plan_id": p, "label": p.title(), "tier_rank": i + 1, "network_by_tpa": {"TPA_INTL": "I_NET"},
                       "defaults": {"area_of_cover": "WW_EXC_USA", "deductible": "D0", "payment_frequency": "ANNUAL",
                                    "module_op": "OP_FULL" if p == "PLUS" else "NONE", "module_evac": "EVAC",
                                    "module_maternity": "NONE"}} for i, p in enumerate(plans)],
            "components": [
                {"component_id": "base", "type": "BASE_TABLE",
                 "sources": [{"sheet": "IPMI Base", "anchor": "A3", "row_dims": [{"dim": "age", "band_map": "ipmi5"}],
                              "col_dims": [{"dim": "plan", "map": "plans"}, {"dim": "gender", "map": "gender"}],
                              "n_rows": len(labs), "n_cols": 4}]},
                {"component_id": "f_area", "type": "FACTOR_TABLE", "family": "area_of_cover", "reference_level": "WW_EXC_USA",
                 "values": {"WW_INC_USA": 1.72, "WW_EXC_USA": 1.0, "REGIONAL": 0.81}},
                {"component_id": "f_ded", "type": "FACTOR_TABLE", "family": "deductible", "keys": ["deductible", "area_of_cover"],
                 "reference_level": "D0",
                 "sources": [{"sheet": "Deductibles", "anchor": "A2", "row_dims": [{"dim": "deductible", "map": "deds"}],
                              "col_dims": [{"dim": "area_of_cover", "map": "areas"}], "n_rows": 4, "n_cols": 3}]},
                {"component_id": "f_freq", "type": "FACTOR_TABLE", "family": "payment_frequency", "reference_level": "ANNUAL",
                 "values": {"ANNUAL": 1.0, "QUARTERLY": 1.03, "MONTHLY": 1.05}},
                {"component_id": "m_op", "type": "MODULE", "family": "module_op", "unit": "PER_MEMBER", "keys": ["plan", "module_op"],
                 "rows": [{"key": {"plan": "CORE", "module_op": "OP_FULL"}, "value": 610.0},
                          {"key": {"plan": "PLUS", "module_op": "OP_FULL"}, "value": 790.0}]},
                {"component_id": "m_evac", "type": "MODULE", "family": "module_evac", "unit": "PER_MEMBER", "keys": ["module_evac"],
                 "values": {"EVAC": 95.0}},
                {"component_id": "m_mat", "type": "MODULE", "family": "module_maternity", "unit": "PER_ELIGIBLE_FEMALE",
                 "keys": ["plan", "module_maternity"],
                 "rows": [{"key": {"plan": "CORE", "module_maternity": "MAT"}, "value": 1350.0},
                          {"key": {"plan": "PLUS", "module_maternity": "MAT"}, "value": 1720.0}]}
            ],
            "formula": {"rounding": 2}
        }],
        "rules": [{"rule_id": "I_R1", "scope": {}, "type": "UW", "parameters": {"medical_underwriting": "FULL"},
                   "text": "Full medical underwriting"}]
    }
    _dump(spec, d / "spec.json")
    return spec


# =============================================================================================== EXPO_SYN
MERIT_TPA = {"TPA_RED": "TPA RED", "TPA_BLUE": "TPA BLUE", "TPA_GREEN": "TPA GREEN"}
MERIT_NET = {"N_PLAT": "PLATINUM", "N_GOLD": "GOLD", "N_SILV": "SILVER", "N_BRNZ": "BRONZE", "N_STD": "STANDARD",
             "N_CLIN": "CLINIC", "N_BASIC": "BASIC"}
RELATIONS = {"EMPLOYEE": "EMPLOYEE", "SPOUSE": "SPOUSE", "CHILD": "CHILD", "PARENT": "PARENT"}
NAT_GROUPS = {"Indian-Subcontinent": "GRP_SOUTH", "Asian": "GRP_EAST", "Western Expat": "GRP_WEST",
              "GCC Arab": "OTHER", "Other Arab": "OTHER", "Other": "OTHER"}


def build_expo(out: Path, alpha_spec_path: Path, contract_path: Path):
    """Synthetic dim_life in the Merit shape (all contract columns), seeded; written premium = rated price under
    CAT_ALPHA at randomly drawn co-pay options x a seeded noise term, so V3 recovers a known implied factor."""
    import pandas as pd

    from pw.evaluator import evaluate
    from pw.spec_parser import parse_catalogue
    d = out / "EXPO_SYN"
    (d / "maps").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    cols = [c for c, _ in contract["tables"]["dim_life"]["columns"]]
    n = 2400
    plans = [f"P{i}" for i in range(1, 8)]
    tpas = list(MERIT_TPA)
    rows = []
    for i in range(n):
        tpa = tpas[int(rng.integers(0, 3))]
        p = plans[int(rng.choice(7, p=[0.05, 0.10, 0.15, 0.20, 0.22, 0.16, 0.12]))]
        rel = ["EMPLOYEE", "SPOUSE", "CHILD", "PARENT"][int(rng.choice(4, p=[0.55, 0.2, 0.22, 0.03]))]
        age = int(np.clip(rng.normal(35 if rel != "CHILD" else 8, 12 if rel != "PARENT" else 6) + (30 if rel == "PARENT" else 0), 0, 80))
        g = "Female" if rng.random() < (0.45 if rel != "SPOUSE" else 0.9) else "Male"
        mar = "MARRIED" if rel in ("SPOUSE", "PARENT") or (rel == "EMPLOYEE" and rng.random() < 0.6) else "SINGLE"
        natg = list(NAT_GROUPS)[int(rng.choice(6, p=[0.35, 0.15, 0.12, 0.1, 0.13, 0.15]))]
        uwy = 2025 if rng.random() < 0.8 else 2024
        cov_days = int(rng.choice([365, 365, 365, 240, 120]))
        rows.append({"tpa": tpa, "plan": p, "rel": rel, "age": age, "g": g, "mar": mar, "natg": natg, "uwy": uwy,
                     "cov_days": cov_days, "op": ["0%", "10%", "20%"][int(rng.choice(3, p=[0.2, 0.6, 0.2]))],
                     "noise": float(np.exp(rng.normal(0.0, 0.04)))})
    # a small unmapped tail (plan label with no plan_map row) and a few REFER cells (age 70+, P6/P7)
    for i in range(0, n, 97):
        rows[i]["plan_label"] = "Plan 9 Legacy"
    for i in range(5, n, 211):
        rows[i]["age"] = 72
        rows[i]["plan"] = "P7"
        rows[i]["rel"] = "PARENT"
    cat = parse_catalogue(alpha_spec_path)
    cells = pd.DataFrame([{"cell_id": i, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A",
                           "tpa": r["tpa"], "plan": r["plan"], "age": r["age"], "gender": GENDER_MAP[r["g"]],
                           "nationality_group": NAT_GROUPS[r["natg"]], "copay_op_diag": r["op"],
                           "maternity_eligible": "Y" if (r["g"] == "Female" and 18 <= r["age"] <= 45) else "N"}
                          for i, r in enumerate(rows)])
    priced, _ = evaluate(cat, cells, {"fill": "default"})
    price = priced.set_index("cell_id")["price"]
    recs = []
    for i, r in enumerate(rows):
        import datetime as _dt
        start_d = _dt.date(r["uwy"], 1 + (i % 12), 1)
        start = start_d.isoformat()
        cov_end = (start_d + _dt.timedelta(days=r["cov_days"] - 1)).isoformat()
        ly = round(r["cov_days"] / 365.0, 6)
        pr = price.loc[i]
        if pr != pr:   # REFER / unpriced: give a premium anyway (the cedant still wrote it)
            pr = 9000.0
        wp = round(pr * ly * r["noise"] * (1.02 if r["tpa"] == "TPA_BLUE" else 1.0), 2)
        rec = {c: None for c in cols}
        rec.update({
            "LifeID": i + 1, "LifeKey": f"SYN|{MERIT_TPA[r['tpa']]}|POL{i // 4:05d}|M{i:06d}",
            "Payer Name": "SYNTHETIC PAYER", "Risk Carrier": "SYNTHETIC CARRIER", "MasterCedantName": "SYNTHETIC CEDANT",
            "TPA": MERIT_TPA[r["tpa"]], "PolKey": f"POL{i // 4:05d}", "MemKey": f"M{i:06d}", "UWY": r["uwy"],
            "PolicyStart": start, "PolicyEndAdj": f"{r['uwy'] + 1}-{1 + (i % 12):02d}-01", "AnnualBasisDays": 365,
            "CovStart": start, "CovEnd": cov_end, "Periods": 1, "CovDays": r["cov_days"], "EarnedDays": r["cov_days"],
            "ZP_Gross": 1, "ZP_Net": 1, "WrittenLY_Gross": ly, "WrittenLY_Net": ly, "EarnedLY_Gross": ly, "EarnedLY_Net": ly,
            "WrittenPrem_Gross": round(wp * 1.18, 2), "WrittenPrem_Net": wp, "EarnedPrem_Gross": round(wp * 1.18, 2),
            "EarnedPrem_Net": wp, "RI Name": "SYNTHETIC RE", "Policy Type": "INDIVIDUAL", "PolicyTypeUsed": "INDIVIDUAL",
            "PolicyTypeSource": "raw", "Relation": RELATIONS[r["rel"]], "Gender": r["g"], "Marital Status": r["mar"],
            "Nationality": "SYNTHETIC", "Region": "REGION A", "Network": MERIT_NET[cat.scopes[0].plan(r["plan"]).network_by_tpa[r["tpa"]]],
            "Plan / Category": r.get("plan_label", f"Plan {r['plan'][1:]}"), "AgeAtInception": r["age"],
            "AgeBand": None, "GroupSize": 1, "GroupSizeBand": "1", "NewRenewal": "Renewal" if i % 3 else "New",
            "NewRenewalSource": "synthetic", "Joiner": 0, "Leaver": 0, "Tenure": 1, "Currency": "AED", "Country": "AE",
            "EndoGroup": "Initial/Renewal in force", "Region Group": "DHA", "Nationality Group": r["natg"],
            "Gender Group": ("Maternity Eligible Female" if (r["g"] == "Female" and 18 <= r["age"] <= 45) else r["g"]),
            "Distribution": ["BROKER", "DIRECT", "AGENCY"][i % 3]})
        recs.append(rec)
    with (d / "dim_life.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for rec in recs:
            w.writerow({k: ("" if v is None else v) for k, v in rec.items()})
    with (d / "run_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Key", "Value"])
        for k, v in [("valuation_date", "2026-06-30"), ("workflow", "synthetic"), ("workflow_version", "synthetic-1"),
                     ("default_premium_basis", "NET"), ("currency", "AED"), ("contract_version", contract["version"])]:
            w.writerow([k, v])

    def wcsv(name, header, data):
        with (d / "maps" / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(data)
    wcsv("segment_map.csv", ["policy_type", "region_group", "product_type", "regulator", "rating_region"],
         [["INDIVIDUAL", "DHA", "INDIVIDUAL", "DHA", "RGN_A"]])
    wcsv("tpa_map.csv", ["source_tpa", "tpa"], [[v, k] for k, v in MERIT_TPA.items()])
    wcsv("plan_map.csv", ["product_type", "rating_region", "tpa", "source_plan", "plan"],
         [["INDIVIDUAL", "RGN_A", "ANY", f"Plan {p[1:]}", p] for p in plans])
    wcsv("network_map.csv", ["tpa", "source_network", "network"], [["ANY", v, k] for k, v in MERIT_NET.items()])
    wcsv("member_category_map.csv", ["product_type", "relation", "member_category"],
         [["ANY", k, v] for k, v in RELATIONS.items()])
    wcsv("nationality_map.csv", ["source_group", "nationality_group"], [[k, v] for k, v in NAT_GROUPS.items()])
    wcsv("value_map.csv", ["dim", "source_value", "value"],
         [["gender", "Male", "M"], ["gender", "Female", "F"], ["marital", "SINGLE", "SINGLE"], ["marital", "MARRIED", "MARRIED"],
          ["maternity_eligible", "Male", "N"], ["maternity_eligible", "Female", "N"],
          ["maternity_eligible", "Maternity Eligible Female", "Y"]])
    _dump({"note": "Synthetic exposure for CAT_ALPHA. Written premium = CAT_ALPHA price at the drawn OP diagnostic co-pay "
                   "x life-years x lognormal(0, 0.04) noise x 1.02 for TPA_BLUE. Plan label 'Plan 9 Legacy' is deliberately "
                   "unmapped; some age-72 P7 parents hit REFER cells.", "seed": SEED, "rows": n}, d / "README.json")


# =============================================================================================== MARKET_SYN (WS2)
SME_NETS = ["CN", "GN", "RN", "RN2", "RN3", "VN"]
SME_LEVERS = ["Room type", "Annual Medical Limit", "PEC limit", "OP consultation deductible", "OP lab / radiology copay",
              "Pharmacy limit", "Pharmacy copay", "IP coinsurance", "Medication type", "Territory",
              "Other adjustment 1", "Other adjustment 2"]
SME_ADDONS = ["Dental", "Optical", "Maternity", "Physiotherapy", "OP Psychiatric", "Alternative Medicine",
              "Nursing at Home", "Routine Health Check-up", "Repatriation"]


def _sme_intake(path: Path, plan: dict):
    """Fictional plan in the SME-INTAKE v2.4 cell layout (only the input cells the adapter reads)."""
    wb = new_workbook(path, title=f"fictional SME intake {plan['pid']}")
    a = wb.add_worksheet("A_Plan")
    for cell, v in [("C5", plan["pid"]), ("C6", plan["name"]), ("C7", plan["insurer"]), ("C8", plan["status"]),
                    ("C9", "Yes"), ("C10", "SME"), ("C11", plan["emirate"]), ("C12", "2026-01-01"),
                    ("C13", plan["period"]), ("C14", "AED"), ("C15", plan["basis"])]:
        a.write(cell, v)
    if plan.get("g2n"):
        a.write_number("C16", plan["g2n"])
    for i, v in enumerate(["Covered from enrolment", 500, 1000, "Yes", 8, 3, 30, "Yes"]):
        a.write(22 + i, 2, v)
    for i in range(10):
        a.write(33 + i, 2, "Yes" if i in plan.get("other_yes", []) else "No")
    b = wb.add_worksheet("B_Rates")
    bands = plan["bands"]
    for j, n in enumerate(SME_NETS):
        b.write(5 + j, 2, "Yes" if n in plan["nets"] else "No")
    for i, (lo, hi) in enumerate(bands):
        b.write_number(15 + i, 1, lo)
        b.write_number(15 + i, 2, hi)
    for j, n in enumerate(SME_NETS):
        c0 = 1 + 4 * j
        for k, h in enumerate(["Principal M", "Principal F", "Dependent M", "Dependent F"]):
            b.write(40, c0 + k, h)
        if n not in plan["nets"]:
            continue
        lvl = plan["nets"][n]
        for i, (lo, hi) in enumerate(bands):
            mid = (lo + min(hi, 80)) / 2
            for k, f in enumerate([1.0, 1.12, 0.93, 1.05]):
                v = round(lvl * (0.6 + 0.011 * mid + 0.0004 * mid * mid) * f / (12 if plan["period"] == "Monthly" else 1), 2)
                b.write_number(41 + i, c0 + k, v)
    for k, lev in enumerate(SME_LEVERS):
        for j, n in enumerate(SME_NETS):
            if n in plan["nets"]:
                b.write(65 + k, 1 + j, plan["design"][lev])
    c = wb.add_worksheet("C_Factors")
    for i, (lev, opt, net, f) in enumerate(plan.get("factors", [])):
        c.write(4 + i, 0, lev)
        c.write(4 + i, 1, opt)
        c.write(4 + i, 2, net)
        c.write_number(4 + i, 3, f)
    d = wb.add_worksheet("D_Optional")
    for i, row in enumerate(plan.get("optional", [])):
        for k, v in enumerate(row):
            d.write(4 + i, k, v)
    e = wb.add_worksheet("E_TOB")
    for k, ben in enumerate(SME_ADDONS):
        lim, cop, inb = plan["package"].get(ben, ("Not Covered", "n/a", "No"))
        e.write(4 + k, 0, ben)
        e.write(4 + k, 1, lim)
        e.write(4 + k, 2, cop)
        e.write(4 + k, 3, inb)
    wb.close()


def build_market_syn(out: Path):
    d = out / "MARKET_SYN"
    (d / "intake").mkdir(parents=True, exist_ok=True)
    base_design = {"Room type": "Private", "Annual Medical Limit": 1000000, "PEC limit": "Up to AML",
                   "OP consultation deductible": "AED 50", "OP lab / radiology copay": "10%", "Pharmacy limit": "Up to AED 5,000",
                   "Pharmacy copay": "20%", "IP coinsurance": "0%", "Medication type": "Branded", "Territory": "UAE only",
                   "Other adjustment 1": "Standard", "Other adjustment 2": "Standard"}
    bands7 = [(0, 17), (18, 29), (30, 39), (40, 49), (50, 59), (60, 64), (65, 100)]
    plans = [
        {"pid": "MKT-ALPINE-2026", "name": "Alpine SME", "insurer": "Fictional Insurer One", "status": "Placed",
         "emirate": "Dubai & Northern Emirates", "period": "Annual", "basis": "Net", "bands": bands7,
         "nets": {"CN": 3900.0, "GN": 3100.0, "RN": 2500.0, "RN3": 1500.0}, "design": base_design,
         "factors": [("OP lab / radiology copay", "0%", "All", 1.035), ("OP lab / radiology copay", "20%", "All", 0.962),
                     ("Room type", "Semi Private", "All", 0.955)],
         "optional": [("Maternity", 10000, "10% Copayment", "All", "Flat per member", "Eligible females (maternity ages)", 2400.0),
                      ("Dental", 2000, "20% Copayment", "All", "Flat per member", "All members", 310.0)],
         "package": {"Maternity": (10000, "10% Copayment", "No"), "Dental": (2000, "20% Copayment", "No"),
                     "Physiotherapy": (10, "20% Copayment", "Yes")}, "other_yes": [0, 4]},
        {"pid": "MKT-BIRCH-2026", "name": "Birch SME", "insurer": "Fictional Insurer Two", "status": "Placed",
         "emirate": "Dubai", "period": "Monthly", "basis": "Gross", "g2n": 0.82,
         "bands": [(0, 17), (18, 39), (40, 59), (60, 100)],
         "nets": {"GN": 3500.0, "RN": 2700.0, "RN2": 2100.0}, "design": {**base_design, "Annual Medical Limit": 500000,
                                                                       "OP lab / radiology copay": "20%", "Room type": "Semi Private"},
         "factors": [("Annual Medical Limit", 1000000, "All", 1.03)],
         "package": {"Maternity": (10000, "10% Copayment", "Yes"), "Optical": (500, "20% Copayment", "No")},
         "other_yes": [4]},
        {"pid": "MKT-CEDAR-2026", "name": "Cedar SME", "insurer": "Fictional Insurer Three", "status": "Placed",
         "emirate": "Dubai", "period": "Annual", "basis": "Net", "bands": bands7,
         "nets": {"CN": 4300.0, "GN": 3300.0, "RN3": 1650.0, "VN": 1250.0},
         "design": {**base_design, "OP lab / radiology copay": "0%", "Pharmacy copay": "10%"},
         "optional": [("Maternity", 15000, "10% Copayment", "GN", "Flat per member", "Married eligible females (maternity ages)", 3300.0),
                      ("Maternity", 15000, "10% Copayment", "All", "Flat per member", "Married eligible females (maternity ages)", 2900.0)],
         "package": {"Maternity": (15000, "10% Copayment", "No"), "Dental": (2000, "20% Copayment", "No")},
         "other_yes": [0, 4, 5]},
    ]
    for p in plans:
        _sme_intake(d / "intake" / f"{p['pid']}.xlsx", p)

    def wcsv(name, header, rows):
        with (d / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
    wcsv("tier_map.csv", ["catalogue_id", "plan", "tier", "weight"],
         [["ANY", n, n, "1"] for n in SME_NETS] +
         [["ANY", "P1", "CN", "1"], ["ANY", "P2", "GN", "1"], ["ANY", "P3", "RN", "1"],      # CAT_ALPHA and its submissions
          ["ANY", "P4", "RN2", "1"], ["ANY", "P5", "RN3", "1"], ["ANY", "P6", "RN3", "0.5"],
          ["ANY", "P6", "VN", "0.5"], ["ANY", "P7", "VN", "1"],
          ["CAT_GAMMA", "G1", "CN", "1"], ["CAT_GAMMA", "G2", "GN", "1"], ["CAT_GAMMA", "G3", "RN", "1"], ["CAT_GAMMA", "G4", "RN3", "1"],
          ["CAT_IPMI", "PLUS", "CN", "1"], ["CAT_IPMI", "CORE", "GN", "1"]])
    wcsv("option_map.csv", ["catalogue_id", "family", "option", "canonical_option"],
         [["ANY", "copay_op_diag", "AED25", "AED 25"], ["ANY", "aml", "1250000", "1500000"]])
    wcsv("standard_cells.csv", ["age", "gender", "member_category", "marital", "maternity_eligible", "nationality_group",
                                "group_size_band", "weight"],
         [[35, "M", "EMPLOYEE", "MARRIED", "N", "OTHER", 25, 40], [32, "F", "EMPLOYEE", "MARRIED", "Y", "OTHER", 25, 25],
          [31, "F", "SPOUSE", "MARRIED", "Y", "OTHER", 25, 15], [6, "M", "CHILD", "SINGLE", "N", "OTHER", 25, 10],
          [8, "F", "CHILD", "SINGLE", "N", "OTHER", 25, 10], [52, "M", "EMPLOYEE", "MARRIED", "N", "OTHER", 25, 8]])
    rel = {"copay_op_diag": {"0%": 1.04, "10%": 1.0, "20%": 0.96, "AED 25": 1.01},
           "aml": {"300000": 0.95, "500000": 0.97, "750000": 0.985, "1000000": 1.0, "1500000": 1.012, "2000000": 1.02}}
    _dump({"_note": "FICTIONAL market relativities for tests (stand-in for a market basis imported at run time).",
           "source": "fictional fixture", "placeholder": True,
           "entries": [{"family": f, "option": o, "network": "ANY", "relativity": v} for f, d_ in rel.items() for o, v in d_.items()]},
          d / "market_basis.json")


# =============================================================================================== RUN_SYN (WS1)
def build_run_syn(out: Path):
    """Synthetic run inputs for B1/B2/TreatyFeed on CAT_ALPHA x EXPO_SYN x SUB_X/SUB_Y (all fictional)."""
    d = out / "RUN_SYN"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "treaty_book_map.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["product_type", "rating_region", "tpa", "treaty_book"])
        w.writerow(["INDIVIDUAL", "RGN_A", "TPA_GREEN", "BOOK_IND_GREEN"])
        w.writerow(["INDIVIDUAL", "RGN_A", "ANY", "BOOK_IND_OTHER"])
    with (d / "experience.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["treaty_book", "earned_prem", "ultimate_claims"])
        w.writerow(["BOOK_IND_GREEN", "1250000.00", "962500.00"])
        w.writerow(["BOOK_IND_OTHER", "2680000.00", "1983200.00"])
    with (d / "terms_scores.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["option_id", "commission_pct", "profit_share_pct", "corridor_pts", "cap_pct", "share_pct"])
        w.writerow(["SUB_X", "17.5", "20", "5", "120", "50"])
        w.writerow(["SUB_Y", "15.0", "25", "0", "110", "30"])
    _dump({"run_id": "RUN_SYN", "expiring": "../CAT_ALPHA/spec.json",
           "exposure": {"dim_life": "../EXPO_SYN/dim_life.csv", "maps": "../EXPO_SYN/maps",
                        "manifest": "../EXPO_SYN/run_manifest.csv", "snapshot_date": "2025-07-01"},
           "treaty": {"book_map": "treaty_book_map.csv", "experience": "experience.csv",
                      "lapse": {"BOOK_IND_GREEN": 0.06, "BOOK_IND_OTHER": 0.04}},
           "v5": {"outlier_band": [0.7, 1.3]},
           "benefit_overrides": [],
           "benchmark": {"market_folders": ["../MARKET_SYN/intake"],
                         "market_catalogues": ["../CAT_GAMMA/spec.json", "../CAT_IPMI/spec.json"],
                         "subjects": ["@expiring", "@options"],
                         "tier_map": "../MARKET_SYN/tier_map.csv", "tier_ladder": ["CN", "GN", "RN", "RN2", "RN3", "VN"],
                         "standard_cells": "../MARKET_SYN/standard_cells.csv", "use_exposure_mix": True,
                         "market_basis": "../MARKET_SYN/market_basis.json", "option_map": "../MARKET_SYN/option_map.csv",
                         "richness_families": ["copay_op_diag", "aml"], "currency": "AED", "fx": {"AED": 1.0, "USD": 3.6725},
                         "basis": "NET", "basis_factors": {}, "gap_share": 0.5, "peer_same_region": False},
           "scorecard": {"weights_file": "../../examples/scorecard_weights.json", "terms_scores": "terms_scores.csv",
                         "panels": [{"panel_id": "PANEL_XY", "lead": "SUB_X", "members": {"SUB_X": 0.6, "SUB_Y": 0.4}}],
                         "grid_step": 0.1, "show_reinsurer_names": False, "market_facing": False,
                         "incumbent_names": []},
           "duckdb": {"memory_limit": "2GB", "threads": 2}}, d / "run_config.json")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "fixtures"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    build_alpha(out)
    build_beta(out)
    build_gamma(out)
    build_delta(out)
    build_retiree(out)
    build_ipmi(out)
    build_expo(out, out / "CAT_ALPHA" / "spec.json", REPO / "contracts" / "merit_model_contract_IP4-8.json")
    build_market_syn(out)
    build_run_syn(out)
    print(f"fixtures written to {out}")


if __name__ == "__main__":
    main()
