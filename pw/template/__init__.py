"""Tender Rates Template generator and submission parser (SPEC §8).

Hidden sheets: ``_KEYS`` (one row per input cell: cell_key, live reference formula, kind, mandatory, key_json, issued
sheet/address) and ``_META`` (structure hash, spec hash, versions). Parsing back needs no mapping (SPEC §8.2).
"""
KEYS_SHEET = "_KEYS"
META_SHEET = "_META"
TEMPLATE_SPEC_VERSION = "1"
GENERATOR_VERSION = "ws0-1"
KINDS = ("RATE", "ADDON", "MULTIPLIER", "TERM")
KEYS_HEADER = ["cell_key", "ref", "kind", "mandatory", "key_json", "issued_sheet", "issued_address"]
