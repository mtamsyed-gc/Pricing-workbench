from _util import raises

from pw import MappingRequired, SpecError
from pw.registry import ANY, BandMap, load_registry, parse_band_label


def test_all_dimensions_present():
    reg = load_registry()
    for code in ["product_type", "regulator", "rating_region", "tpa", "plan", "network", "network_option", "age", "gender",
                 "marital", "member_category", "maternity_eligible", "nationality_group", "salary_band", "group_size_band",
                 "copay_op_diag", "ded_consult", "copay_pharmacy", "copay_ip", "pharmacy_limit", "aml", "module_maternity",
                 "module_dental", "module_optical", "module_op", "module_evac", "area_of_cover", "deductible", "currency",
                 "payment_frequency", "rating_basis_age"]:
        reg.dim(code)
    assert "RETIREE" in reg.dim("product_type").values and "IPMI" in reg.dim("product_type").values
    assert not reg.dim("currency").cell_key and not reg.dim("rating_basis_age").cell_key


def test_hierarchy_and_wildcard():
    reg = load_registry()
    assert reg.parent_of("member_category", "SPOUSE") == "DEPENDANT"
    assert reg.parent_of("member_category", "EMPLOYEE") == "PRINCIPAL"
    assert reg.parent_of("member_category", "DOMESTIC_UAE_SPONSOR") == "DOMESTIC"
    reg.check_value("member_category", "PRINCIPAL")
    reg.check_value("gender", ANY)
    raises(MappingRequired, reg.check_value, "gender", "X")
    raises(MappingRequired, reg.check_value, "gender", ANY, allow_any=False)


def test_single_year_age_band_maps():
    assert parse_band_label("18-30") == (18, 30)
    assert parse_band_label("00–17") == (0, 17)
    assert parse_band_label("60+") == (60, 120)
    assert parse_band_label("55") == (55, 55)
    raises(MappingRequired, parse_band_label, "Above sixty")
    bm = BandMap.from_spec("b", {"parse": ["0-17", "18-40", "41+"]})
    assert bm.label_of(17) == "0-17" and bm.label_of(41) == "41+" and bm.range_of("18-40") == (18, 40)
    raises(SpecError, BandMap.from_spec, "bad", {"0-20": [0, 20], "20-30": [20, 30]})


def test_dimension_order_is_stable():
    reg = load_registry()
    assert reg.sort_dims(["gender", "age", "plan", "tpa"]) == ["tpa", "plan", "age", "gender"]
