"""Tender Rates Template generator (SPEC §8.0–§8.2).

Workbook: Cover, Existing Rates (expiring catalogue in the same block layout, derived co-pay multipliers, V2 flags),
Factor Tables, Add-ons, one rate sheet per template sheet (one block per product x rating region x TPA:
age x network/plan x columns at the reference co-pay), Terms, hidden _KEYS and _META. Input cells are yellow,
unlocked, validated (> 0) and keyed; the structure is locked when protect_structure is on.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import SpecError
from ..io_excel import a1, new_workbook, parse_a1, quote_sheet
from ..model import canonical_key_str
from ..registry import ANY, load_registry
from . import GENERATOR_VERSION, KEYS_HEADER, KEYS_SHEET, META_SHEET, TEMPLATE_SPEC_VERSION
from .spec import normalise, spec_hash

TITLE_ROWS = 3       # title, basis statement, blank
BLOCK_HEAD = 3       # block title, plan header, column header
BLOCK_GAP = 2
LABEL_COLS = 2       # section, row label


@dataclass
class InputCell:
    cell_key: str
    kind: str
    sheet: str
    row: int              # 0-based
    col: int
    mandatory: bool
    keys: list            # expansion: canonical keys the value applies to
    refer: bool = False
    block_id: str | None = None
    label: str | None = None

    @property
    def address(self) -> str:
        return a1(self.row + 1, self.col + 1)

    def key_json(self) -> str:
        return json.dumps(self.keys, sort_keys=True, ensure_ascii=False)


@dataclass
class Layout:
    nspec: dict
    rate_sheets: list = field(default_factory=list)   # [{sheet, blocks:[{block, origin_row, ...}]}]
    cells: list = field(default_factory=list)         # InputCell (RATE + REFER markers)
    other_inputs: list = field(default_factory=list)  # TERM / MULTIPLIER / ADDON cells (filled at write time)

    def keys_rows(self) -> list:
        """Rows exactly as written to _KEYS (without the live ref formula): inputs first, then REFER markers."""
        allc = [c for c in self.cells if not c.refer] + self.other_inputs
        refer_c = [c for c in self.cells if c.refer]
        return [[c.cell_key, ("REFER" if c.refer else c.kind), bool(c.mandatory) and not c.refer, c.key_json(),
                 c.sheet, c.address] for c in allc + refer_c]

    def structure_hash(self) -> str:
        return hash_keys_rows(self.keys_rows(), [s["sheet"] for s in self.rate_sheets], self.nspec.get("tender_id"))


def hash_keys_rows(rows: list, rate_sheets: list, tender_id) -> str:
    """Structure hash (SPEC §8.2): over the _KEYS content (key, kind, mandatory, expansion, issued position),
    the rate sheet names and the tender id. Values and dates are excluded."""
    items = sorted([str(r[0]), str(r[1]), bool(r[2]), str(r[3]), str(r[4]), str(r[5])] for r in rows)
    payload = {"v": TEMPLATE_SPEC_VERSION, "sheets": list(rate_sheets), "cells": items, "tender_id": tender_id}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _row_in(refer_val, row_val) -> bool:
    if isinstance(refer_val, list) and isinstance(row_val, list):
        return refer_val[0] <= row_val[0] and row_val[1] <= refer_val[1]
    return refer_val == row_val


def _is_refer(block, key: dict) -> bool:
    for rk in block["refer_cells"]:
        if all(d in key and _row_in(v, key[d]) for d, v in rk.items()):
            return True
    return False


def compute_layout(nspec: dict) -> Layout:
    """Positions of every rate input cell (no workbook needed: used by the parser's positional fallback)."""
    reg = load_registry()
    lay = Layout(nspec=nspec)
    seen = set()
    for sh in nspec["sheets"]:
        sname = sh["sheet_name"]
        r = TITLE_ROWS
        blocks = []
        for b in sh["blocks"]:
            ncols = len(b["columns"])
            origin = r
            data0 = r + BLOCK_HEAD
            bk = {k: v for k, v in b["block_key"].items() if v is not None}
            for ri, row in enumerate(b["rows"]):
                for pi, p in enumerate(b["plans"]):
                    for ci, col in enumerate(b["columns"]):
                        keys = [{**bk, "plan": p["plan_id"], **rk, **ck}
                                for rk in [row["key"], *row.get("alt_keys", [])] for ck in col["keys"]]
                        primary = keys[0]
                        ckey = canonical_key_str(primary, reg.order)
                        if ckey in seen:
                            raise SpecError(f"duplicate template cell key {ckey} (sheet {sname}, block {b['block_id']})")
                        seen.add(ckey)
                        lay.cells.append(InputCell(cell_key=ckey, kind="RATE", sheet=sname, row=data0 + ri,
                                                   col=LABEL_COLS + pi * ncols + ci, mandatory=bool(sh.get("mandatory", True)),
                                                   keys=keys, refer=_is_refer(b, primary), block_id=b["block_id"],
                                                   label=f"{p['label']} / {row['label']} / {col['label']}"))
            blocks.append({"block": b, "origin_row": origin, "data_row": data0, "ncols": ncols})
            r = data0 + len(b["rows"]) + BLOCK_GAP
        lay.rate_sheets.append({"sheet": sname, "spec": sh, "blocks": blocks, "end_row": r})
    return lay


@dataclass
class GeneratedTemplate:
    path: Path
    structure_hash: str
    spec_hash: str
    n_inputs: int
    n_refer: int
    layout: Layout


class _Fmt:
    def __init__(self, wb):
        self.title = wb.add_format({"bold": True, "font_size": 14})
        self.sub = wb.add_format({"italic": True, "font_color": "#555555"})
        self.bold = wb.add_format({"bold": True})
        self.block = wb.add_format({"bold": True, "font_size": 12, "bg_color": "#DDEBF7"})
        self.hdr = wb.add_format({"bold": True, "align": "center", "border": 1, "bg_color": "#F2F2F2", "text_wrap": True})
        self.lab = wb.add_format({"border": 1})
        self.inp = wb.add_format({"bg_color": "#FFFF99", "border": 1, "locked": False, "num_format": "#,##0.00"})
        self.inp_txt = wb.add_format({"bg_color": "#FFFF99", "border": 1, "locked": False, "text_wrap": True})
        self.refer = wb.add_format({"bg_color": "#D9D9D9", "border": 1, "font_color": "#555555", "align": "center"})
        self.ro = wb.add_format({"border": 1, "num_format": "#,##0.00"})
        self.fac = wb.add_format({"border": 1, "num_format": "0.0000"})
        self.flag = wb.add_format({"border": 1, "bg_color": "#F4B6B6", "num_format": "#,##0.00"})
        self.outlier = wb.add_format({"bg_color": "#F8CBAD"})
        self.wrap = wb.add_format({"text_wrap": True, "valign": "top"})


def generate_template(spec: dict, out_path: Path, expiring=None) -> GeneratedTemplate:
    nspec = normalise(spec)
    lay = compute_layout(nspec)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    created = _dt.datetime.fromisoformat(nspec["issue_date"]) if nspec.get("issue_date") else None
    wb = new_workbook(out_path, created=created, title=f"Tender rates {nspec['tender_id']}")
    f = _Fmt(wb)
    opts = nspec["options"]
    refs = nspec["reference_sheets"]
    protect = opts["protect_structure"]

    ws_cover = wb.add_worksheet("Cover")
    ws_er = wb.add_worksheet("Existing Rates") if refs.get("existing_rates") else None
    ws_fac = wb.add_worksheet("Factor Tables") if refs.get("factor_tables") else None
    ws_add = wb.add_worksheet("Add-ons") if refs.get("addons") else None
    ws_tob = wb.add_worksheet("TOB Summary") if refs.get("tob_summary") else None
    rate_ws = {s["sheet"]: wb.add_worksheet(s["sheet"]) for s in lay.rate_sheets}
    ws_terms = wb.add_worksheet("Terms") if refs.get("terms") else None
    ws_keys = wb.add_worksheet(KEYS_SHEET)
    ws_meta = wb.add_worksheet(META_SHEET)

    # ---- rate sheets
    er_pos = write_rate_sheets(wb, f, lay, nspec, rate_ws, protect, ws_er=ws_er, expiring=expiring)

    # ---- existing rates
    v2 = None
    if ws_er is not None:
        ws_er.write(0, 0, "Existing Rates - expiring catalogue, same blocks (read only)", f.title)
        ws_er.set_column(0, 1, 14)
        if expiring is None:
            ws_er.write(1, 0, "No expiring catalogue supplied to the generator.", f.sub)
        else:
            from ..gates import v2_block_consistency
            ws_er.write(1, 0, f"Source: {expiring.catalogue_id} v{expiring.version}. Base table values at the reference "
                              "options (before factor tables).", f.sub)
            v2 = v2_block_consistency(expiring)
            _write_existing(ws_er, f, lay, expiring, er_pos, v2)
        if protect:
            ws_er.protect()

    # ---- factor tables / add-ons / tob
    if ws_fac is not None:
        _write_factors(ws_fac, f, nspec, expiring, lay, v2)
        if protect:
            ws_fac.protect("", {"select_locked_cells": True, "select_unlocked_cells": True})
    if ws_add is not None:
        _write_addons(ws_add, f, nspec, expiring, lay)
        if protect:
            ws_add.protect("", {"select_locked_cells": True, "select_unlocked_cells": True})
    if ws_tob is not None:
        _write_tob(ws_tob, f, expiring)
        if protect:
            ws_tob.protect()
    if ws_terms is not None:
        ws_terms.write(0, 0, "Terms", f.title)
        ws_terms.write(1, 0, "Structured terms of the submission; free text allowed in comments.", f.sub)
        ws_terms.set_column(0, 0, 28)
        ws_terms.set_column(1, 1, 60)
        fields = list(nspec["terms_fields"]) + (["benefit_comments"] if opts["allow_benefit_comments"] else [])
        for i, fld in enumerate(fields):
            r = 3 + i
            ws_terms.write(r, 0, fld.replace("_", " ").capitalize(), f.lab)
            ws_terms.write_blank(r, 1, None, f.inp_txt)
            lay.other_inputs.append(InputCell(cell_key=f"term={fld}", kind="TERM", sheet="Terms", row=r, col=1,
                                              mandatory=False, keys=[{"term": fld}], label=fld))
        if protect:
            ws_terms.protect("", {"select_locked_cells": True, "select_unlocked_cells": True})

    shash = lay.structure_hash()
    sphash = spec_hash(nspec)

    # ---- cover
    ws_cover.set_column(0, 0, 28)
    ws_cover.set_column(1, 1, 90)
    ws_cover.write(0, 0, f"Tender rates template - {nspec['cedant']} - {nspec['tender_id']}", f.title)
    lines = [("Deadline", nspec["deadline"]), ("Contact", nspec.get("contact") or ""),
             ("Currency / basis", f"{nspec['currency']} / {nspec['premium_basis']}"),
             ("Basis statement", "Submit base rates only, at the reference co-pay options stated on each sheet. Co-pay, "
                                 "annual limit, TPA, nationality and network-option adjustments are the factor tables "
                                 "shown in Factor Tables (read only unless a proposed column is offered)."),
             ("TPA basis", "The rate in each TPA block is BEFORE the TPA factor: the issued TPA factor in Factor Tables "
                           "is applied on top. Do not build the TPA difference into the block as well."),
             ("Instructions", "Fill the yellow cells with annual premiums per member greater than 0. Grey cells are "
                              "referred. Do not insert, delete or rename sheets, rows or columns."),
             ("Template version", f"{TEMPLATE_SPEC_VERSION} / generator {GENERATOR_VERSION}"),
             ("Structure hash", shash)]
    for i, (k, v) in enumerate(lines):
        ws_cover.write(2 + i, 0, k, f.bold)
        ws_cover.write(2 + i, 1, v, f.wrap)
    r = 3 + len(lines)
    ws_cover.write(r, 0, "Sheet directory", f.bold)
    add_fill = nspec["reference_sheets"].get("addons") == "FILL"
    directory = [(n, "fill the submitted column (rider rates; a blank cell means not quoted)" if n == "Add-ons" and add_fill
                  else "read only")
                 for n, w in (("Existing Rates", ws_er), ("Factor Tables", ws_fac), ("Add-ons", ws_add),
                              ("TOB Summary", ws_tob)) if w is not None]
    directory += [(s["sheet"], f"fill yellow cells ({len(s['blocks'])} block(s): "
                               + ", ".join(bl["block"]["label"] for bl in s["blocks"]) + ")") for s in lay.rate_sheets]
    if ws_terms is not None:
        directory.append(("Terms", "fill"))
    for i, (n, d) in enumerate(directory):
        ws_cover.write(r + 1 + i, 0, n)
        ws_cover.write(r + 1 + i, 1, d)
    if any(row.get("placeholder") for s in nspec["sheets"] for b in s["blocks"] for row in b["rows"]):
        ws_cover.write(r + 2 + len(directory), 0, "Note", f.bold)
        ws_cover.write(r + 2 + len(directory), 1, "Rows marked * carry placeholder age-band labels pending the cedant.", f.wrap)
    if protect:
        ws_cover.protect()

    # ---- _KEYS / _META
    krows = lay.keys_rows()
    allc = [r for r in krows if r[1] != "REFER"]
    refer_c = [r for r in krows if r[1] == "REFER"]
    meta = [("tender_id", nspec["tender_id"]), ("cedant", nspec["cedant"]), ("structure_hash", shash),
            ("spec_hash", sphash), ("template_spec_version", nspec["template_spec_version"]),
            ("generator_version", GENERATOR_VERSION), ("issue_date", nspec.get("issue_date") or ""),
            ("currency", nspec["currency"]), ("premium_basis", nspec["premium_basis"]),
            ("allow_proposed_multipliers", str(opts["allow_proposed_multipliers"])),
            ("n_inputs", str(len(allc))), ("n_refer", str(len(refer_c)))]
    write_keys_meta(ws_keys, ws_meta, krows, meta, protect)
    wb.close()
    return GeneratedTemplate(path=out_path, structure_hash=shash, spec_hash=sphash, n_inputs=len(allc),
                             n_refer=len(refer_c), layout=lay)


def write_keys_meta(ws_keys, ws_meta, krows: list, meta: list, protect: bool):
    """Hidden _KEYS (one row per input cell with its live reference formula) and _META (SPEC §8.2)."""
    ws_keys.write_row(0, 0, KEYS_HEADER)
    for i, (ckey, kind, mand, kj, sheet, addr) in enumerate(krows):
        ws_keys.write_string(1 + i, 0, ckey)
        rr, cc = parse_a1(addr)
        ws_keys.write_formula(1 + i, 1, f"={quote_sheet(sheet)}!{a1(rr, cc, absolute=True)}", None, "")
        ws_keys.write_string(1 + i, 2, kind)
        ws_keys.write_boolean(1 + i, 3, mand)
        ws_keys.write_string(1 + i, 4, kj)
        ws_keys.write_string(1 + i, 5, sheet)
        ws_keys.write_string(1 + i, 6, addr)
    ws_keys.hide()
    ws_meta.write_row(0, 0, ["key", "value"])
    for i, (k, v) in enumerate(meta):
        ws_meta.write_string(1 + i, 0, k)
        ws_meta.write_string(1 + i, 1, str(v))
    ws_meta.hide()
    if protect:
        ws_keys.protect()
        ws_meta.protect()


def default_rate_subtitle(sh: dict, nspec: dict) -> str:
    basis = ", ".join(f"{k} = {v}" for k, v in sorted((sh.get("copay_basis") or {}).items()))
    return (f"Base rates only ({nspec['currency']}, {nspec['premium_basis']} basis, annual per member). "
            f"Reference options: {basis or 'as per Factor Tables'}. Fill the yellow cells.")


def write_rate_sheets(wb, f, lay: Layout, nspec: dict, rate_ws: dict, protect: bool, subtitle=None, ws_er=None,
                      expiring=None) -> dict:
    """Rate sheets (shared by the tender template and the cedant workbook, SPEC §8.2 / §8.5): one block per
    product x rating region x TPA, yellow keyed input cells, numeric validation, REFER cells. Returns the Existing
    Rates row position per block (tender template)."""
    opts = nspec["options"]
    subtitle = subtitle or default_rate_subtitle
    er_pos = {}
    er_row = TITLE_ROWS
    for rs in lay.rate_sheets:
        ws = rate_ws[rs["sheet"]]
        sh = rs["spec"]
        ws.write(0, 0, sh.get("title") or rs["sheet"], f.title)
        ws.write(1, 0, subtitle(sh, nspec), f.sub)
        ws.set_column(0, 0, 16)
        ws.set_column(1, 1, 14)
        maxc = LABEL_COLS
        for bl in rs["blocks"]:
            b = bl["block"]
            r0 = bl["origin_row"]
            title = f"{b['label']} - {sh['product_type']} {sh.get('rating_region') or ''}".strip()
            if b.get("comment"):
                title += f"  [{b['comment']}]"
            ws.write(r0, 0, title, f.block)
            ws.write(r0 + 1, 0, "Section", f.hdr)
            ws.write(r0 + 1, 1, "Age band", f.hdr)
            ws.write(r0 + 2, 0, "", f.hdr)
            ws.write(r0 + 2, 1, "", f.hdr)
            for pi, p in enumerate(b["plans"]):
                c0 = LABEL_COLS + pi * bl["ncols"]
                lab = p["label"] + (f" ({p['network']})" if p.get("network") else "")
                if bl["ncols"] > 1:
                    ws.merge_range(r0 + 1, c0, r0 + 1, c0 + bl["ncols"] - 1, lab, f.hdr)
                else:
                    ws.write(r0 + 1, c0, lab, f.hdr)
                for ci, col in enumerate(b["columns"]):
                    ws.write(r0 + 2, c0 + ci, col["label"], f.hdr)
            for ri, row in enumerate(b["rows"]):
                ws.write(bl["data_row"] + ri, 0, row.get("section") or "", f.lab)
                ws.write(bl["data_row"] + ri, 1, row["label"] + (" *" if row.get("placeholder") else ""), f.lab)
            maxc = max(maxc, LABEL_COLS + len(b["plans"]) * bl["ncols"])
            last_r = bl["data_row"] + len(b["rows"]) - 1
            last_c = LABEL_COLS + len(b["plans"]) * bl["ncols"] - 1
            ws.data_validation(bl["data_row"], LABEL_COLS, last_r, last_c,
                               {"validate": "decimal", "criteria": ">", "value": 0, "ignore_blank": True,
                                "error_title": "Rate", "error_message": "Enter a rate greater than 0."})
            er_pos[b["block_id"]] = er_row + (bl["data_row"] - bl["origin_row"])
            if opts.get("outlier_shading") and ws_er is not None and expiring is not None:
                lo, hi = opts["outlier_band"]
                tl = a1(er_pos[b["block_id"]] + 1, LABEL_COLS + 1)
                ws.conditional_format(bl["data_row"], LABEL_COLS, last_r, last_c,
                                      {"type": "formula", "format": f.outlier,
                                       "criteria": f"=AND(ISNUMBER({a1(bl['data_row'] + 1, LABEL_COLS + 1)}),"
                                                   f"ISNUMBER('Existing Rates'!{tl}),"
                                                   f"OR({a1(bl['data_row'] + 1, LABEL_COLS + 1)}/'Existing Rates'!{tl}<{lo},"
                                                   f"{a1(bl['data_row'] + 1, LABEL_COLS + 1)}/'Existing Rates'!{tl}>{hi}))"})
            er_row += (bl["data_row"] - bl["origin_row"]) + len(b["rows"]) + BLOCK_GAP
        ws.set_column(LABEL_COLS, maxc, 12)
        if protect:
            ws.protect("", {"format_columns": True, "format_rows": True, "select_locked_cells": True,
                            "select_unlocked_cells": True})
    for c in lay.cells:
        ws = rate_ws[c.sheet]
        if c.refer:
            b = next(bl["block"] for rs in lay.rate_sheets for bl in rs["blocks"] if bl["block"]["block_id"] == c.block_id)
            ws.write_string(c.row, c.col, b["refer_text"], f.refer)
        else:
            ws.write_blank(c.row, c.col, None, f.inp)

    return er_pos


# ------------------------------------------------------------------------------------------------------------------
def _match_scope(cat, sh, tpa):
    for s in cat.scopes:
        if s.product_type == sh["product_type"] and (s.rating_region == sh.get("rating_region")) and \
                (tpa in s.tpa_set or ANY in s.tpa_set):
            return s
    return None


def _write_existing(ws, f, lay, cat, er_pos, v2):
    from ..evaluator import lookup_component
    reg = load_registry()
    r = TITLE_ROWS
    for rs in lay.rate_sheets:
        sh = rs["spec"]
        for bl in rs["blocks"]:
            b = bl["block"]
            ws.write(r, 0, f"{rs['sheet']} / {b['label']}", f.block)
            dr = er_pos[b["block_id"]]
            for pi, p in enumerate(b["plans"]):
                c0 = LABEL_COLS + pi * bl["ncols"]
                ws.write(r + 1, c0, p["label"], f.hdr)
                for ci, col in enumerate(b["columns"]):
                    ws.write(r + 2, c0 + ci, col["label"], f.hdr)
            for ri, row in enumerate(b["rows"]):
                ws.write(dr + ri, 0, row.get("section") or "", f.lab)
                ws.write(dr + ri, 1, row["label"], f.lab)
            scope = _match_scope(cat, sh, b["tpa"])
            cells = [c for c in lay.cells if c.block_id == b["block_id"]]
            if scope is None:
                ws.write(r + 1, 0, "no matching expiring scope", f.sub)
            else:
                base = next(c for c in scope.components if c.type == "BASE_TABLE")
                probes, pos = [], []
                for c in cells:
                    k = c.keys[0]
                    if isinstance(k.get("age"), str):
                        continue
                    probes.append({d: (v[0] if isinstance(v, list) else v) for d, v in k.items() if d in base.keys})
                    pos.append(c)
                res = lookup_component(cat, scope.scope_id, base, probes, reg).set_index("cell_id") if probes else None
                flagged = set()
                if v2 is not None and len(v2):
                    for fr in v2[(v2["scope_id"] == scope.scope_id) & v2["flagged"]].itertuples():
                        flagged.add(fr.cell_key)
                for i, c in enumerate(pos):
                    rr = dr + (c.row - bl["data_row"])
                    if res is None or i not in res.index:
                        ws.write_string(rr, c.col, "n/a", f.lab)
                    elif res.loc[i, "__status"] == "REFER":
                        ws.write_string(rr, c.col, "REFER", f.refer)
                    else:
                        ws.write_number(rr, c.col, float(res.loc[i, "__value"]), f.ro)
            r = dr + len(b["rows"]) + BLOCK_GAP
    if v2 is not None and len(v2):
        r += 1
        ws.write(r, 0, "Co-pay blocks: derived multipliers and V2 flags (cells deviating from the flat multiplier)", f.block)
        r += 1
        hdr = ["scope_id", "level", "cell", "source ref", "reference value", "source value", "multiplier", "expected (derived)",
               "deviation", "resolution"]
        ws.write_row(r, 0, hdr, f.hdr)
        mults = v2.drop_duplicates(["scope_id", "level"])
        for m in mults.itertuples():
            r += 1
            ws.write_row(r, 0, [m.scope_id, m.level, "ALL (flat)", "", "", "", m.multiplier, "", "", m.multiplier_source])
        for fr in v2[v2["flagged"]].itertuples():
            r += 1
            ws.write_row(r, 0, [fr.scope_id, fr.level, fr.cell_key, fr.source_ref or ""])
            ws.write_number(r, 4, fr.reference_value, f.ro)
            ws.write_number(r, 5, fr.source_value, f.flag)
            ws.write_number(r, 6, fr.multiplier, f.fac)
            ws.write_number(r, 7, fr.expected_value, f.ro)
            ws.write_number(r, 8, fr.deviation, f.ro)
            ws.write_string(r, 9, fr.resolution)


def _write_factors(ws, f, nspec, cat, lay, v2):
    ws.write(0, 0, "Factor tables (read only): applied by the cedant to the submitted base rates", f.title)
    ws.set_column(0, 6, 16)
    r = 2
    opts = nspec["options"]
    tables = []
    if cat is not None:
        for s in cat.scopes:
            for c in s.components:
                if c.type == "FACTOR_TABLE":
                    tables.append((s.scope_id, c))
    if not tables and not nspec.get("reference_factor_tables"):
        ws.write(r, 0, "Factor tables are issued with the expiring catalogue (not supplied to the generator).", f.sub)
        return
    for sid, c in tables:
        ref = c.reference_level if c.reference_level is not None else json.dumps(c.reference_level_by_key, sort_keys=True)
        ws.write(r, 0, f"{sid} / {c.component_id} ({c.family}); reference: {ref}", f.block)
        r += 1
        keys = list(c.keys)
        ws.write_row(r, 0, keys + ["factor"] + (["proposed"] if opts["allow_proposed_multipliers"] else []), f.hdr)
        for row in c.rows:
            r += 1
            for j, k in enumerate(keys):
                v = row["key"][k]
                ws.write_string(r, j, f"{v[0]}-{v[1]}" if isinstance(v, list) else str(v), f.lab)
            ws.write_number(r, len(keys), float(row["value"]), f.fac)
            if opts["allow_proposed_multipliers"]:
                ckey = f"multiplier|scope={sid}|component={c.component_id}|" + canonical_key_str(row["key"], load_registry().order)
                ws.write_blank(r, len(keys) + 1, None, f.inp)
                lay.other_inputs.append(InputCell(cell_key=ckey, kind="MULTIPLIER", sheet="Factor Tables", row=r,
                                                  col=len(keys) + 1, mandatory=False,
                                                  keys=[{"scope_id": sid, "component_id": c.component_id, **row["key"]}]))
        r += 2
    for t in nspec.get("reference_factor_tables") or []:
        ws.write(r, 0, t["title"], f.block)
        r += 1
        ws.write_row(r, 0, list(t["columns"]), f.hdr)
        for row in t.get("rows", []):
            r += 1
            ws.write_row(r, 0, row)
        r += 2


def _write_addons(ws, f, nspec, cat, lay):
    mode = nspec["reference_sheets"]["addons"]
    ws.write(0, 0, f"Add-on modules ({'fill' if mode == 'FILL' else 'read only'})", f.title)
    ws.set_column(0, 6, 16)
    r = 2
    mods = [(s.scope_id, c) for s in (cat.scopes if cat else []) for c in s.components if c.type == "MODULE"]
    if not mods:
        ws.write(r, 0, "No add-on modules in the supplied catalogue.", f.sub)
        return
    reg = load_registry()
    for sid, c in mods:
        ws.write(r, 0, f"{sid} / {c.component_id} ({c.family}, {c.unit}, {c.mode})", f.block)
        r += 1
        ws.write_row(r, 0, list(c.keys) + ["expiring"] + (["submitted"] if mode == "FILL" else []), f.hdr)
        for row in c.rows:
            r += 1
            for j, k in enumerate(c.keys):
                v = row["key"][k]
                ws.write_string(r, j, f"{v[0]}-{v[1]}" if isinstance(v, list) else str(v), f.lab)
            if row["value"] is None:
                ws.write_string(r, len(c.keys), "REFER", f.refer)
            else:
                ws.write_number(r, len(c.keys), float(row["value"]), f.ro)
            if mode == "FILL":
                ckey = f"addon|scope={sid}|component={c.component_id}|" + canonical_key_str(row["key"], reg.order)
                ws.write_blank(r, len(c.keys) + 1, None, f.inp)
                lay.other_inputs.append(InputCell(cell_key=ckey, kind="ADDON", sheet="Add-ons", row=r, col=len(c.keys) + 1,
                                                  mandatory=False, keys=[{"scope_id": sid, "component_id": c.component_id,
                                                                          **row["key"]}]))
        r += 2


def _write_tob(ws, f, cat):
    ws.write(0, 0, "Table of benefits summary (read only)", f.title)
    ws.write_row(2, 0, ["scope", "plan", "benefit", "value", "condition"], f.hdr)
    r = 3
    for s in (cat.scopes if cat else []):
        for b in s.benefits:
            ws.write_row(r, 0, [s.scope_id, b.plan_id, b.benefit_code, "" if b.value is None else str(b.value),
                                b.condition_text or ""])
            r += 1
