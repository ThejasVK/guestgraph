from guestgraph.measure import in_holdout, lift, simulate_outcomes


def test_holdout_is_deterministic_and_about_the_right_size():
    ids = [f"G{i}" for i in range(20000)]
    share = sum(in_holdout(g, "c1") for g in ids) / len(ids)
    assert 0.13 < share < 0.17
    assert in_holdout("G42", "c1") == in_holdout("G42", "c1")


def test_lift_recovers_a_known_effect():
    ids = [f"G{i}" for i in range(30000)]
    rep = lift("c1", simulate_outcomes(ids, "c1", base_rate=0.3, true_lift=0.25))
    assert 0.15 < rep.relative_lift < 0.35
    assert rep.significant


def test_no_effect_is_not_significant_most_of_the_time():
    ids = [f"G{i}" for i in range(5000)]
    rep = lift("c2", simulate_outcomes(ids, "c2", true_lift=0.0, seed=5))
    assert abs(rep.relative_lift) < 0.12


def test_required_sample_size_is_sane():
    from guestgraph.measure import required_n_per_group
    n = required_n_per_group(0.30, 0.25)
    assert 500 < n < 800          # ~ 600 per group for 30% -> 37.5%
