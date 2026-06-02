from services.external import compute_external_costs
def test_costs_sum():
    flags = {"gs1": True, "qes": True, "cmmc_l2_c3pao": False}
    res = compute_external_costs(flags)
    assert res["requires_external"] is True
    assert res["sum_min_eur"] >= 35
