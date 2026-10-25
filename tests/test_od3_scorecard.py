"""OD3 / CR #22 (owner, 25 Oct 2026): SHARE on an absolute scale (share of the order filled), NO_SPREAD flag when the
single options do not separate on a criterion, and the cedant example's weights file."""
import json

import numpy as np
import pandas as pd
from _util import REPO, raises, requires, tmpdir
from openpyxl import load_workbook

from pw import SpecError
from pw.scorecard import (directions, flip_points, grid, normalise_absolute, one_at_a_time, score, validate_weights,
                          write_pack)


def _inp(rows):
    return pd.DataFrame([{"option_id": o, "criterion": c, "metric": c.lower(), "value": v, "source": "test",
                          "submitted_text": None} for o, c, v in rows])


def test_share_absolute_scale_hand_checked():
    s = normalise_absolute(pd.Series([50.0, 30.0, 150.0, -5.0, np.nan]))
    assert s.iloc[:4].tolist() == [50.0, 30.0, 100.0, 0.0] and np.isnan(s.iloc[4])
    inp = _inp([("X", "PRICE", 1.00), ("Y", "PRICE", 0.95), ("X", "SHARE", 50), ("Y", "SHARE", 30)])
    card, rank = score(inp, {"PRICE": 0.8, "SHARE": 0.2})
    sh = card[card["criterion"] == "SHARE"].set_index("option_id")
    assert sh["normalised"].to_dict() == {"X": 50.0, "Y": 30.0}           # min-max would have given 100 / 0
    assert (sh["scale_note"] == "ABSOLUTE").all()
    sc = rank.set_index("option_id")["score"]
    assert abs(sc["X"] - (0.8 * 0 + 0.2 * 50)) < 1e-12 and abs(sc["Y"] - (0.8 * 100 + 0.2 * 30)) < 1e-12


def test_panel_capacity_credited_when_singles_tie_on_share():
    """The case that motivated the rule: every single quote offers 100%; a panel's capacity no longer reads as a tie
    by construction, and a partial panel is not credited above a full placement."""
    inp = _inp([("X", "PRICE", 1.00), ("Y", "PRICE", 0.98), ("X", "SHARE", 40), ("Y", "SHARE", 40),
                ("P", "PRICE", 1.00), ("P", "SHARE", 80), ("Q", "PRICE", 1.00), ("Q", "SHARE", 120)])
    kinds = {"X": "OPTION", "Y": "OPTION", "P": "PANEL", "Q": "PANEL"}
    card, rank = score(inp, {"PRICE": 0.5, "SHARE": 0.5}, kinds=kinds)
    sh = card[card["criterion"] == "SHARE"].set_index("option_id")["normalised"].to_dict()
    assert sh == {"P": 80.0, "Q": 100.0, "X": 40.0, "Y": 40.0}
    sc = rank.set_index("option_id")["score"]
    assert abs(sc["Q"] - (0.5 * 0 + 0.5 * 100)) < 1e-12 and abs(sc["P"] - (0.5 * 0 + 0.5 * 80)) < 1e-12
    assert sc["Q"] > sc["P"]                                                # more capacity, up to a full placement


def test_no_spread_flag_and_pack_note():
    inp = _inp([("A", "PRICE", 1.00), ("B", "PRICE", 1.05), ("A", "COMMISSION", 15.0), ("B", "COMMISSION", 15.0)])
    w = {"PRICE": 0.7, "COMMISSION": 0.3}
    card, rank = score(inp, w)
    notes = card.drop_duplicates("criterion").set_index("criterion")["scale_note"].to_dict()
    assert notes == {"PRICE": "", "COMMISSION": "NO_SPREAD"}
    assert (card[card["criterion"] == "COMMISSION"]["normalised"] == 100.0).all()
    oat = one_at_a_time(inp, w)
    with tmpdir() as d:
        p = write_pack(d / "p.xlsx", "T", inp, card, rank, oat, flip_points(oat), grid(inp, w), w, {}, None)
        text = " ".join(str(v) for ws in load_workbook(p).worksheets for row in ws.iter_rows(values_only=True) for v in row if v)
        assert "NO_SPREAD: every single option has the same value on COMMISSION" in text


def test_share_direction_cannot_be_reversed():
    raises(SpecError, directions, {"SHARE": "LOWER"})
    assert directions({"SHARE": "HIGHER"})["SHARE"] == "HIGHER"


@requires("examples/ufic_2027")
def test_cedant_example_weights_file():
    w = json.loads((REPO / "examples" / "ufic_2027" / "scorecard_weights.json").read_text(encoding="utf-8"))["weights"]
    validate_weights(w)
    assert w == {"PRICE": 0.35, "PRICE_BENEFIT_ADJ": 0.10, "ROBUSTNESS_SPREAD": 0.05, "UNPRICED_SHARE": 0.10,
                 "V5_FLAG_SHARE": 0.05, "COMMISSION": 0.20, "PROFIT_SHARE": 0.05, "CORRIDOR": 0.05, "CAP": 0.0, "SHARE": 0.05}
    price = w["PRICE"] + w["PRICE_BENEFIT_ADJ"] + w["ROBUSTNESS_SPREAD"] + w["UNPRICED_SHARE"] + w["V5_FLAG_SHARE"]
    assert abs(price - 0.65) < 1e-12
