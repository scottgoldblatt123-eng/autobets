"""Starter library: well-known automation ideas from the Betfair trading community (Bet Angel's shared automation files and forum), rebuilt from scratch as AutoBets scripts.
Only the ideas are used; the wording, rules and numbers are ours. They are templates to add to your library (switched off), read, tweak and test in practice mode.
Some Bet Angel bots lean on features we do not have; those are listed separately in UNSUPPORTED with the reason."""
from __future__ import annotations

SOURCE = "Idea from the Bet Angel community automation files, rebuilt for AutoBets"


def _c(**k):
    return k


def _back(stake=10, basis="stake"):
    return [{"type": "back", "price": "best", "stake": stake, "basis": basis, "persistence": "CANCEL"}]


def _lay(stake=10, basis="stake"):
    return [{"type": "lay", "price": "best", "stake": stake, "basis": basis, "persistence": "CANCEL"}]


def _rule(i, kind, when, then, **x):
    return {"id": i, "kind": kind, "when": when, "then": then, **x}


IP = _c(type="in_play", value=True)
G = [{"type": "green"}]
CLOSE = [{"type": "close"}]
STOP = [{"type": "close"}, {"type": "stop"}]


def _tk(op, v):
    return _c(type="ticks_from_entry", op=op, value=v)


def _r1():
    return _c(type="rule_matched", rule="r1")


def _s(id, sport, title, summary, attach, caveats, rules, desc=None):
    return {"id": id, "sport": sport, "title": title, "summary": summary, "attach": attach, "caveats": caveats, "source": SOURCE,
            "script": {"name": f"Starter: {title}", "sport": sport, "description": desc or summary, "rules": rules}}


STARTERS: list[dict] = [
    # ---------------------------------------------------------------- tennis
    _s("t-lay-early-break", "tennis", "Lay a player who goes a break up early",
       "For players who often give leads back. When the player breaks serve early in a set (three games or fewer played), lay him by liability. Hedge when he is broken back, when he goes two breaks up, or when the set ends.",
       "Attach to the player you think wastes early leads (add the other player too if both do).",
       ["Break counts are worked out from the games and who is serving, so they can be wrong for a game or two if the feed is late.", "Practice-mode testing first: a break-up player often does win the set."],
       [_rule("r1", "entry", [IP, _c(type="breaks_diff", op=">=", value=1), _c(type="set_games_total", op="<=", value=3)], _lay(10, "liability"), repeat=5),
        _rule("r2", "exit", [_r1(), _c(type="breaks_diff", op="<=", value=0)], G),
        _rule("r3", "exit", [_r1(), _c(type="breaks_diff", op=">=", value=2)], G),
        _rule("r4", "exit", [_r1(), _c(type="set_games_total", op="<=", value=0)], G),
        _rule("r5", "safety", [_tk("<=", -15)], STOP)]),
    _s("t-lay-fav-broken", "tennis", "Lay the favourite when his serve is broken",
       "Lay the pre-match favourite for £10 when he has been broken and is a game behind, as long as his price is still short enough to be worth it (2.5 or less). Close for a small loss if he breaks straight back; green up when the set ends.",
       "Attach to the match favourite.",
       ["Price limit 2.5 is a setting you can change in the editor."],
       [_rule("r1", "entry", [IP, _c(type="breaks_diff", op="<=", value=-1), _c(type="set_games_diff", op="<=", value=-1), _c(type="price", op="<=", value=2.52, ref="last")], _lay(10), repeat=5),
        _rule("r2", "exit", [_r1(), _c(type="breaks_diff", op=">=", value=0)], CLOSE),
        _rule("r3", "exit", [_r1(), _c(type="set_games_total", op="<=", value=0)], G),
        _rule("r4", "safety", [_tk("<=", -15)], STOP)]),
    _s("t-back-fav-lost-set1", "tennis", "Back the favourite after he loses set 1, green up in stages",
       "At the start of set 2, if the favourite lost set 1, back him for £10. If he goes a break up while serving, take out half. Green up fully when set 3 starts (he levelled) or if he loses set 2.",
       "Attach to the pre-match favourite.",
       ["Best-of-five men's matches need a longer exit; this version finishes when set 3 starts."],
       [_rule("r1", "entry", [IP, _c(type="set_number", op="==", value=2), _c(type="sets_diff", op="<=", value=-1), _c(type="set_games_total", op="<=", value=0)], _back(10)),
        _rule("r2", "exit", [_r1(), _c(type="serving", value=True), _c(type="breaks_diff", op=">=", value=1)], [{"type": "close", "percent": 50}]),
        _rule("r3", "exit", [_r1(), _c(type="set_number", op=">=", value=3)], G),
        _rule("r4", "safety", [_tk("<=", -15)], STOP)]),
    _s("t-back-server", "tennis", "Back the server every game",
       "At the start of each of the player's own service games (0-0), if his price is 2.5 or less, back him for £10; green up when the game ends. Repeats all match. Works best for men's matches where holds are common.",
       "Attach to a player; attach the other player as a second Plan row to trade both servers.",
       ["Backs at the very start of the game, so the price may move before the bet is matched.", "Tie-breaks are not handled specially."],
       [_rule("r1", "entry", [IP, _c(type="serving", value=True), _c(type="game_score_is", me="0", opp="0"), _c(type="price", op="<=", value=2.5, ref="last")], _back(10), repeat=100),
        _rule("r2", "exit", [_r1(), _c(type="serving", value=False)], G),
        _rule("r3", "safety", [_tk("<=", -10)], STOP)]),
    _s("t-lay-server", "tennis", "Lay the server every game",
       "The mirror image: at the start of each of the player's service games, lay him for £10 and green up when the game ends. Suits players who are weak on serve.",
       "Attach to a player who is weak on serve.",
       ["Laying a short-priced server costs more per game when he holds, which is most of the time."],
       [_rule("r1", "entry", [IP, _c(type="serving", value=True), _c(type="game_score_is", me="0", opp="0")], _lay(10), repeat=100),
        _rule("r2", "exit", [_r1(), _c(type="serving", value=False)], G),
        _rule("r3", "safety", [_tk("<=", -10)], STOP)]),
    _s("t-break-point", "tennis", "Trade the break point",
       "When the player is serving and faces a break point, back him for £10; green up when the game ends. If he saves it, the price shortens and you profit; if he loses the game you take a loss. Change Back to Lay in the editor to trade it the other way.",
       "Attach to the player you want to trade on serve.",
       ["Needs the live point score from the tennis feed; if the feed lags the break point may be over before the bet is placed."],
       [_rule("r1", "entry", [IP, _c(type="break_point", side="against")], _back(10), repeat=100),
        _rule("r2", "exit", [_r1(), _c(type="serving", value=False)], G),
        _rule("r3", "safety", [_tk("<=", -10)], STOP)]),
    _s("t-back-two-points-behind", "tennis", "Back a server who is two points behind",
       "When the player is serving and falls two or more points behind in the game (for example 0-30), back him for £10 and green up when the game ends, whoever wins it. Repeats all match.",
       "Attach to a player who tends to hold from behind.",
       ["Choose players with a good record of holding under pressure."],
       [_rule("r1", "entry", [IP, _c(type="serving", value=True), _c(type="game_points_diff", op="<=", value=-2)], _back(10), repeat=100),
        _rule("r2", "exit", [_r1(), _c(type="serving", value=False)], G),
        _rule("r3", "safety", [_tk("<=", -10)], STOP)]),
    _s("t-lay-two-points-behind", "tennis", "Lay a server who is two points behind",
       "Same trigger as above but lay the player instead, for players who tend to drop serve from behind. Green up when the game ends.",
       "Attach to a player who often gets broken from 0-30.",
       [], [_rule("r1", "entry", [IP, _c(type="serving", value=True), _c(type="game_points_diff", op="<=", value=-2)], _lay(10), repeat=100),
            _rule("r2", "exit", [_r1(), _c(type="serving", value=False)], G),
            _rule("r3", "safety", [_tk("<=", -10)], STOP)]),
    _s("t-lay-set1-winner", "tennis", "Lay the first-set winner at the start of set 2",
       "For evenly matched players. If the player who won set 1 is trading at 1.56 or less at the start of set 2, lay him for £10. Take out some of the position if he goes a game behind, more if he goes two games behind, and close at the end of set 2.",
       "Attach to the pre-match favourite.",
       ["The staged exits are 25% and then 35% of the full hedge."],
       [_rule("r1", "entry", [IP, _c(type="set_number", op="==", value=2), _c(type="sets_diff", op=">=", value=1), _c(type="set_games_total", op="<=", value=0), _c(type="price", op="<=", value=1.56, ref="last")], _lay(10)),
        _rule("r2", "exit", [_r1(), _c(type="set_games_diff", op="<=", value=-1)], [{"type": "close", "percent": 25}]),
        _rule("r3", "exit", [_r1(), _c(type="set_games_diff", op="<=", value=-2)], [{"type": "close", "percent": 35}]),
        _rule("r4", "exit", [_r1(), _c(type="set_number", op=">=", value=3)], G),
        _rule("r5", "safety", [_tk("<=", -15)], STOP)]),
    _s("t-back-easy-set1-winner", "tennis", "Back the set-1 winner if he won it by three games or more",
       "At the start of set 2, back the player for £10 if he won set 1 by three or more games (6-3 or better). Green up when set 3 starts.",
       "Attach to either player; add both to cover whoever wins set 1.",
       ["Only fires for the player who won set 1 comfortably."],
       [_rule("r1", "entry", [IP, _c(type="set_number", op="==", value=2), _c(type="set_games_total", op="<=", value=0), _c(type="prev_set_games_diff", op=">=", value=3)], _back(10)),
        _rule("r2", "exit", [_r1(), _c(type="set_number", op=">=", value=3)], G),
        _rule("r3", "safety", [_tk("<=", -12)], STOP)]),
    _s("t-lay-fav-hedge-first-break", "tennis", "Lay the favourite at the start of each set, hedge on the first break",
       "Lay the favourite by £10 liability at the start of each set. As soon as either player breaks serve, green up. If nobody breaks by 6-6, close then.",
       "Attach to the match favourite.",
       ["Re-arms each set up to 5 times."],
       [_rule("r1", "entry", [IP, _c(type="set_games_total", op="<=", value=0)], _lay(10, "liability"), repeat=5),
        _rule("r2", "exit", [_r1(), _c(type="breaks_diff", op=">=", value=1)], G),
        _rule("r3", "exit", [_r1(), _c(type="breaks_diff", op="<=", value=-1)], G),
        _rule("r4", "exit", [_r1(), _c(type="set_games_total", op=">=", value=12)], G),
        _rule("r5", "safety", [_tk("<=", -15)], STOP)]),
    _s("t-lay-set-and-break-up", "tennis", "Lay a player who is a set and a break up",
       "For evenly matched players. When a player has won a set and then goes a break up, his price is low so laying has small liability; lay him for £10. If he is broken back, take out half; green up at the end of the set.",
       "Attach to a player in a match with no strong favourite (add both players).",
       ["The original idea filters to evenly matched games before the match; here you choose the matches."],
       [_rule("r1", "entry", [IP, _c(type="sets_diff", op=">=", value=1), _c(type="breaks_diff", op=">=", value=1)], _lay(10)),
        _rule("r2", "exit", [_r1(), _c(type="breaks_diff", op="<=", value=0)], [{"type": "close", "percent": 50}]),
        _rule("r3", "exit", [_r1(), _c(type="set_number", op=">=", value=3)], G),
        _rule("r4", "safety", [_tk("<=", -15)], STOP)]),
    # -------------------------------------------------------------- football
    _s("f-lay-draw", "football", "Lay the draw before kick-off, green up after a goal",
       "One minute before kick-off lay the draw for £10. When a goal is scored (and the market has settled to a normal spread) green up. If there is no goal you hold to the end.",
       "Attach to the Draw runner in Match Odds.",
       ["Holds to full time if the game stays 0-0 and a draw loses the full liability.", "Goals come from the live football feed, not from watching the price."],
       [_rule("r1", "entry", [_c(type="in_play", value=False), _c(type="minutes_to_start", op="<=", value=1), _c(type="minutes_to_start", op=">=", value=0)], _lay(10)),
        _rule("r2", "exit", [_r1(), _c(type="goals_total", op=">=", value=1), _c(type="spread_ticks", op="<=", value=3)], G)]),
    _s("f-lay-draw-ht", "football", "Lay the draw at half time if it is 0-0",
       "At half time, if the score is 0-0, lay the draw for £10, then green up if a goal arrives in the second half. Best on matches with no strong favourite.",
       "Attach to the Draw runner in Match Odds. Choose matches without a strong favourite.",
       ["The favourite filter in the original (price above 2.30 before kick-off) is a manual choice here."],
       [_rule("r1", "entry", [_c(type="half_time", value=True), _c(type="goals_total", op="==", value=0)], _lay(10)),
        _rule("r2", "exit", [_r1(), _c(type="goals_total", op=">=", value=1), _c(type="spread_ticks", op="<=", value=3)], G)]),
    _s("f-lay-over25-15", "football", "Lay Over 2.5 before kick-off, green up at 15 minutes",
       "Just before kick-off lay Over 2.5 goals with a £10 liability, then close the trade after 15 minutes. You win if there is no early goal (the Over price drifts) and lose a little if there is. Also works on Over 1.5.",
       "Attach to Over 2.5 Goals in the Over/Under 2.5 market. Pick matches where an early goal is unlikely.",
       [],
       [_rule("r1", "entry", [_c(type="in_play", value=False), _c(type="minutes_to_start", op="<=", value=1), _c(type="minutes_to_start", op=">=", value=0)], _lay(10, "liability")),
        _rule("r2", "exit", [_r1(), IP, _c(type="minute", op=">=", value=15)], G),
        _rule("r3", "safety", [_tk("<=", -20)], STOP)]),
    _s("f-back-over15", "football", "Back Over 1.5 goals before kick-off",
       "Back Over 1.5 for £10 just before kick-off and hold to the end. A simple baseline; the idea is to pick matches where goals are likely.",
       "Attach to Over 1.5 Goals in the Over/Under 1.5 market.",
       ["No exit: the stake is at risk until full time."],
       [_rule("r1", "entry", [_c(type="in_play", value=False), _c(type="minutes_to_start", op="<=", value=5), _c(type="minutes_to_start", op=">=", value=0)], _back(10))]),
    _s("f-under15-ht", "football", "Lay Under 1.5 in the second half if it is still 0-0",
       "At half time if there has been no goal, lay Under 1.5 for £10 once its price is 2.0 or below (waiting for it to fall if needed). Stop out for a small loss if the price shortens 30 ticks with no goal. After a goal, stop out if the price comes back to where you laid. A second goal wins the full stake.",
       "Attach to Under 1.5 Goals. Choose matches where second-half goals are likely.",
       ["Stop distances are ticks and can be changed in the editor."],
       [_rule("r1", "entry", [IP, _c(type="minute", op=">=", value=45), _c(type="goals_total", op="==", value=0), _c(type="price", op="<=", value=2.0, ref="lay")], _lay(10)),
        _rule("r2", "exit", [_r1(), _c(type="goals_total", op="==", value=0), _tk("<=", -30)], CLOSE),
        _rule("r3", "exit", [_r1(), _c(type="goals_total", op=">=", value=1), _tk("<=", 0)], CLOSE),
        _rule("r4", "safety", [_tk("<=", -40)], STOP)]),
    _s("f-back-under25-10", "football", "Back Under 2.5 before kick-off, green up at 10 minutes",
       "Back Under 2.5 for £10 just before kick-off and green up at the 10th minute. If a goal comes early the position closes for a loss.",
       "Attach to Under 2.5 Goals. Make sure the market is set to go in play.",
       ["The bet is placed pre-match: if the market does not go in play you cannot close it."],
       [_rule("r1", "entry", [_c(type="in_play", value=False), _c(type="minutes_to_start", op="<=", value=1), _c(type="minutes_to_start", op=">=", value=0)], _back(10)),
        _rule("r2", "exit", [_r1(), IP, _c(type="minute", op=">=", value=10)], G),
        _rule("r3", "safety", [_tk("<=", -20)], STOP)]),
    _s("f-back-under25-after-goal", "football", "Back Under 2.5 after an early goal",
       "Wait for a goal in the first 15 minutes, then back Under 2.5 for £10 and take 6 ticks profit. If a second goal arrives first, close out for the loss.",
       "Attach to Under 2.5 Goals. Use markets with decent volume so the price is reliable.",
       ["The original takes a percentage profit; this uses ticks."],
       [_rule("r1", "entry", [IP, _c(type="minute", op="<=", value=15), _c(type="goals_total", op="==", value=1)], _back(10)),
        _rule("r2", "exit", [_r1(), _tk(">=", 6)], G),
        _rule("r3", "exit", [_r1(), _c(type="goals_total", op=">=", value=2)], CLOSE),
        _rule("r4", "safety", [_tk("<=", -20)], STOP)]),
]

UNSUPPORTED = [
    {"title": "Lay the current correct score in the final 10 minutes", "sport": "football", "reason": "A script is attached to one runner, but this one needs to pick a different correct-score runner as the score changes."},
    {"title": "Dutching correct scores (fixed or variable profit)", "sport": "football", "reason": "Dutching needs one script to place sized bets on several runners at once, which scripts cannot do yet. The Manual screen has a dutching tool."},
    {"title": "Track Over 1.5 to trigger lays on Over 2.5 / Signal when goals are scored", "sport": "football", "reason": "These read one market to act in another. Goals are already known from the live feed, so most of these can be rewritten using goals and minute instead."},
    {"title": "Back the server if he won the last game easily", "sport": "tennis", "reason": "Needs the result of the previous game's points (40-0 or 40-15), and the feed only gives the current game."},
    {"title": "Trade the server with a few seconds' delay", "sport": "tennis", "reason": "Scripts cannot wait a number of seconds yet. 'Back the server every game' is the nearest."},
]
