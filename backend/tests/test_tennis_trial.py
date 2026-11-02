import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from tennis_trial import surname, split_event, coverage, same_player


def test_surname_and_split():
    assert surname("N. Djokovic") == "djokovic" and surname("Carlos Alcaraz") == "alcaraz"
    assert surname("Ana Konjuh") == "konjuh" and surname("J. Sinner") == "sinner"
    assert split_event("Alcaraz v Sinner") == ("alcaraz", "sinner")
    assert split_event("Madrid Open") is None


def test_coverage_is_order_independent():
    hit, miss, dbl = coverage(["Alcaraz v Sinner", "Zverev v Rune", "A/B v C/D"], [("Jannik Sinner", "Carlos Alcaraz")])
    assert hit == ["Alcaraz v Sinner"] and miss == ["Zverev v Rune"] and dbl == ["A/B v C/D"]


def test_name_variants():
    assert same_player("Da Merida", "Daniel Merida Aguilar") and same_player("Se Baez", "Sebastian Baez")
    assert same_player("Ig Buse", "Ignacio Buse") and not same_player("A Zverev", "Musetti")
