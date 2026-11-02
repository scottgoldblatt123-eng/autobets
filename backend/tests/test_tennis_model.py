from autobets.tennis import model

# Values taken from the workbook's Sheet1 (Siniakova v Badosa) with its tour averages back-solved
AVG = model.Averages(return_pts=42.978, opp_hold=65.978)
SIN = {"service_pts": 57.6, "return_pts": 46.3, "hold": 68.8, "opp_hold": 57.8}
BAD = {"service_pts": 61.9, "return_pts": 43.1, "hold": 76.9, "opp_hold": 67.8}


def test_adjusted_service_points_match_workbook():
    assert abs(model.adj_service_pts(SIN, BAD, AVG) - 57.47840237) < 1e-3
    assert abs(model.adj_service_pts(BAD, SIN, AVG) - 58.57840237) < 1e-3


def test_projected_hold_matches_workbook():
    assert abs(model.projected_hold(SIN, BAD, AVG) - 70.62218935) < 1e-3
    assert abs(model.projected_hold(BAD, SIN, AVG) - 68.72218935) < 1e-3


def test_probability_and_odds_sum_and_invert():
    p = model.price(SIN, BAD, AVG)
    assert abs(p["p_a"] + p["p_b"] - 100) < 1e-9
    assert abs(p["odds_a"] * p["p_a"] - 100) < 1e-9
    assert p["p_a"] > 50 > p["p_b"]
