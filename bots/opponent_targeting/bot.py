"""
PERSONALITY 8: TARGETING + DISCIPLINE (hybrid)
===============================================
Combines the strengths of two winning approaches:

  FROM OPPONENT TARGETING (core — what's winning):
    - Bluff MORE vs tight opponents (+10% freq), never vs calling stations
    - Kelly 0.85 — stronger value bets when we have edge
    - BLUFF_FREQUENCY 0.22 — apply real pressure
    - Opponent-aware bet sizing (bigger vs loose-passive)

  FROM RISK BOT (safety — what prevents busts):
    - Commitment caps (preflop 30%, post-flop equity-tiered)
    - Opponent-aware preflop discount (fold to tight 3-bettors)
    - Streets-aware uncertainty (flop: 0.08, turn: 0.05, river: 0.01)
    - Opponent profile pre-bias (works from hand 5, not 15)
    - Range-aware preflop equity discount

Strategy: Exploit aggressively, but never bust. Targeting's
aggression accumulates chips. Risk's caps prevent giving them back.
"""

import eval7
import random

# ─────────────────────────────────────────────────────────
# PRECOMPUTED PREFLOP EQUITY TABLE
# (Same table from both source bots)
# ─────────────────────────────────────────────────────────

PREFLOP_EQ_TABLE = {
    (14,14,False): [0.852,0.730,0.636,0.563,0.506],
    (13,13,False): [0.824,0.684,0.579,0.497,0.434],
    (12,12,False): [0.800,0.646,0.533,0.454,0.393],
    (11,11,False): [0.775,0.614,0.504,0.424,0.365],
    (10,10,False): [0.752,0.580,0.470,0.393,0.336],
    (9, 9,False):  [0.721,0.545,0.437,0.363,0.309],
    (8, 8,False):  [0.693,0.513,0.405,0.334,0.283],
    (7, 7,False):  [0.663,0.481,0.376,0.306,0.258],
    (6, 6,False):  [0.635,0.451,0.348,0.281,0.235],
    (5, 5,False):  [0.607,0.422,0.322,0.258,0.215],
    (4, 4,False):  [0.579,0.394,0.297,0.235,0.195],
    (3, 3,False):  [0.553,0.369,0.275,0.216,0.178],
    (2, 2,False):  [0.528,0.345,0.254,0.198,0.162],
    (14,13,True):  [0.670,0.502,0.398,0.329,0.282],
    (14,13,False): [0.641,0.467,0.365,0.299,0.254],
    (14,12,True):  [0.659,0.487,0.382,0.314,0.268],
    (14,12,False): [0.628,0.449,0.348,0.283,0.240],
    (14,11,True):  [0.647,0.471,0.366,0.299,0.253],
    (14,11,False): [0.615,0.431,0.331,0.267,0.225],
    (14,10,True):  [0.635,0.453,0.350,0.284,0.239],
    (14,10,False): [0.602,0.414,0.315,0.253,0.212],
    (14,9,True):   [0.607,0.421,0.320,0.257,0.215],
    (14,8,True):   [0.592,0.403,0.303,0.241,0.201],
    (14,7,True):   [0.580,0.388,0.289,0.229,0.190],
    (14,6,True):   [0.568,0.375,0.277,0.218,0.180],
    (14,5,True):   [0.560,0.366,0.268,0.210,0.172],
    (13,12,True):  [0.631,0.462,0.357,0.290,0.245],
    (13,12,False): [0.599,0.423,0.321,0.258,0.216],
    (13,11,True):  [0.619,0.444,0.340,0.274,0.230],
    (13,11,False): [0.585,0.404,0.305,0.243,0.203],
    (13,10,True):  [0.607,0.428,0.324,0.259,0.216],
    (13,10,False): [0.571,0.386,0.289,0.229,0.190],
    (12,11,True):  [0.607,0.430,0.326,0.261,0.218],
    (12,11,False): [0.572,0.390,0.291,0.230,0.191],
    (12,10,True):  [0.596,0.413,0.310,0.246,0.204],
    (12,10,False): [0.558,0.371,0.274,0.216,0.178],
    (11,10,True):  [0.577,0.396,0.296,0.233,0.193],
    (11,10,False): [0.539,0.353,0.259,0.202,0.166],
    (10,9,True):   [0.557,0.375,0.277,0.218,0.179],
    (10,9,False):  [0.517,0.332,0.241,0.187,0.153],
    (9,8,True):    [0.539,0.355,0.260,0.202,0.165],
    (9,8,False):   [0.497,0.311,0.223,0.172,0.140],
    (8,7,True):    [0.521,0.337,0.243,0.188,0.153],
    (8,7,False):   [0.478,0.292,0.207,0.159,0.128],
}


def lookup_preflop_equity(hole_cards, n_opponents):
    if len(hole_cards) != 2:
        return None
    r1, s1 = hole_cards[0][0], hole_cards[0][1]
    r2, s2 = hole_cards[1][0], hole_cards[1][1]
    rank_map = {"A":14,"K":13,"Q":12,"J":11,"T":10,
                "9":9,"8":8,"7":7,"6":6,"5":5,"4":4,"3":3,"2":2}
    v1, v2 = rank_map.get(r1,0), rank_map.get(r2,0)
    if v1 < v2:
        v1, v2, s1, s2 = v2, v1, s2, s1
    is_pair = (v1 == v2)
    is_suited = (s1 == s2) and not is_pair
    key = (v1, v2, is_suited)
    row = PREFLOP_EQ_TABLE.get(key)
    if row is None:
        return None
    idx = min(n_opponents - 1, 4)
    return row[idx]


# ─────────────────────────────────────────────────────────
# SECTION 1: CARD UTILITIES
# ─────────────────────────────────────────────────────────

def rank_value(rank):
    return {"A":14,"K":13,"Q":12,"J":11,"T":10,
            "9":9,"8":8,"7":7,"6":6,"5":5,"4":4,"3":3,"2":2}.get(rank, 0)


# ─────────────────────────────────────────────────────────
# SECTION 2: PREFLOP FALLBACK SCORER
# ─────────────────────────────────────────────────────────

def evaluate_preflop_strength(hole_cards, n_opponents=1):
    if len(hole_cards) != 2:
        return 0.30
    r1, s1 = hole_cards[0][0], hole_cards[0][1]
    r2, s2 = hole_cards[1][0], hole_cards[1][1]
    v1, v2 = rank_value(r1), rank_value(r2)
    if v1 < v2:
        v1, v2 = v2, v1
    if r1 == r2:
        base = 0.56 + (v1 - 2) * (0.30 / 12)
    else:
        base = (v1 + v2) / 27.0
        if s1 == s2: base += 0.04
        gap = v1 - v2
        base += 0.03 if gap <= 2 else (0.01 if gap == 3 else 0.0)
        if v2 < 6: base -= 0.05
    base = max(0.0, min(base, 1.0))
    scale = 0.82 ** (n_opponents - 1)
    return base * scale


# ─────────────────────────────────────────────────────────
# SECTION 3: MULTI-OPPONENT EQUITY (Monte Carlo)
# ─────────────────────────────────────────────────────────

def calculate_equity(hole_cards, community_cards, n_opponents=1, n_sims=1000):
    n_opponents = max(1, min(n_opponents, 5))
    try:
        my_cards    = [eval7.Card(c) for c in hole_cards]
        board_cards = [eval7.Card(c) for c in community_cards]
        cards_needed = 5 - len(board_cards)
        wins = 0
        ties = 0
        for _ in range(n_sims):
            deck = eval7.Deck()
            for c in my_cards + board_cards:
                deck.cards.remove(c)
            deck.shuffle()
            opp_hands = [deck.cards[i*2 : i*2+2] for i in range(n_opponents)]
            board_run  = deck.cards[n_opponents*2 : n_opponents*2 + cards_needed]
            full_board = board_cards + board_run
            my_hand    = my_cards + full_board
            my_score   = eval7.evaluate(my_hand)
            opp_scores = [eval7.evaluate(oh + full_board) for oh in opp_hands]
            best_opp   = max(opp_scores)
            if my_score > best_opp:
                wins += 1
            elif my_score == best_opp:
                ties += 1
        return (wins + ties * 0.5) / n_sims
    except Exception:
        return 1.0 / (n_opponents + 1)


# ─────────────────────────────────────────────────────────
# SECTION 4: POT ODDS
# ─────────────────────────────────────────────────────────

def calculate_pot_odds(pot, amount_owed):
    if amount_owed <= 0:
        return 0.0
    return amount_owed / (pot + amount_owed)


# ─────────────────────────────────────────────────────────
# SECTION 5: ACTIVE OPPONENT COUNTING + POSITION
# ─────────────────────────────────────────────────────────

def count_active_opponents(players, my_seat):
    if not players:
        return 1
    total_opponents = len(players) - 1
    if total_opponents <= 0:
        return 1
    folded_count = 0
    for i, p in enumerate(players):
        seat = p.get("seat", i) if isinstance(p, dict) else i
        if seat == my_seat:
            continue
        if isinstance(p, dict):
            folded = (p.get("folded") or p.get("is_folded") or
                      p.get("out") or p.get("status") == "folded")
            stack  = p.get("stack", 1)
            if folded or stack <= 0:
                folded_count += 1
    return max(1, total_opponents - folded_count)


def get_my_seat(game_state):
    return game_state.get("seat_to_act", 0)


def get_position(seat_to_act, n_players):
    if n_players <= 1:
        return 0.5
    return seat_to_act / max(n_players - 1, 1)


def is_in_position(position_float):
    return position_float > 0.5


# ─────────────────────────────────────────────────────────
# SECTION 6: OPPONENT MODELLING — with Risk's pre-bias
#
# FROM RISK: profile data is usable from hand 5, not hand 15.
# Means exploitation kicks in EARLIER in matches.
# ─────────────────────────────────────────────────────────

opponent_profiles  = {}
_seen_action_ids   = set()

def update_opponent_models(action_log, my_seat):
    global opponent_profiles, _seen_action_ids
    for i, action in enumerate(action_log):
        uid = (i, action.get("seat"), action.get("action"), action.get("amount", 0))
        if uid in _seen_action_ids:
            continue
        _seen_action_ids.add(uid)
        seat = action.get("seat")
        if seat is None or seat == my_seat:
            continue
        if seat not in opponent_profiles:
            opponent_profiles[seat] = {
                "total_actions":      0,
                "aggressive_actions": 0,
                "voluntary_entries":  0,
                "hands_seen":         0,
                "_in_this_hand":      False,
            }
        p   = opponent_profiles[seat]
        act = action.get("action", "")
        st  = action.get("street", "")
        p["total_actions"] += 1
        if act in ("raise", "bet", "all_in"):
            p["aggressive_actions"] += 1
        if st == "preflop" and act in ("call", "raise"):
            if not p["_in_this_hand"]:
                p["voluntary_entries"] += 1
                p["_in_this_hand"] = True


def get_opponent_stats(seat):
    """
    Returns (aggression 0-1, is_loose bool).
    PRE-BIAS: works from hand 5, blended with neutral until hand 15.
    """
    p = opponent_profiles.get(seat)
    if not p or p["total_actions"] < 5:
        return 0.50, False
    raw_agg = p["aggressive_actions"] / p["total_actions"]
    raw_vpip = p["voluntary_entries"] / max(p["hands_seen"], 1)
    n = p["total_actions"]
    if n >= 15:
        return raw_agg, raw_vpip > 0.35
    elif n >= 10:
        # 60% observed + 40% neutral
        return raw_agg * 0.60 + 0.50 * 0.40, (raw_vpip * 0.60 + 0.25 * 0.40) > 0.35
    else:
        # 30% observed + 70% neutral
        return raw_agg * 0.30 + 0.50 * 0.70, (raw_vpip * 0.30 + 0.25 * 0.70) > 0.35


def primary_opponent_seat(players, my_seat):
    best, best_n = None, 0
    for seat, p in opponent_profiles.items():
        if seat != my_seat and p["total_actions"] > best_n:
            best, best_n = seat, p["total_actions"]
    return best


# ─────────────────────────────────────────────────────────
# SECTION 7: BET SIZING — KELLY CRITERION
#
# FROM TARGETING: KELLY_FRACTION = 0.85 (stronger Kelly)
# FROM RISK: streets-aware uncertainty for tighter flop play
# ─────────────────────────────────────────────────────────

KELLY_FRACTION   = 0.85   # FROM TARGETING — stronger Kelly
MIN_BET_FRACTION = 0.40   # FROM TARGETING — always bet meaningful sizes
MAX_BET_FRACTION = 1.00


def kelly_bet_fraction(equity, n_opponents=1, street="river"):
    """
    Kelly bet sizing with streets-aware uncertainty.
    Flop: noisy (2 cards to come), higher uncertainty.
    River: exact, low uncertainty.
    """
    # FROM RISK: streets-aware uncertainty
    if street == "flop":
        uncertainty = 0.08
    elif street == "turn":
        uncertainty = 0.05
    else:
        uncertainty = 0.01

    p = equity - uncertainty
    if p <= 0.5:
        return 0.0

    raw_fraction = (2.0 * p - 1.0) / (1.0 - p)
    bet_fraction = raw_fraction * KELLY_FRACTION

    if n_opponents >= 3:
        bet_fraction *= 0.85
    elif n_opponents == 2:
        bet_fraction *= 0.92

    return max(MIN_BET_FRACTION, min(bet_fraction, MAX_BET_FRACTION))


def calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                            your_bet_this_street=0,
                            n_opponents=1, opp_aggression=0.5, opp_is_loose=False,
                            street="river"):
    """Compute raise amount using Kelly + opponent-aware sizing (FROM TARGETING)."""
    bet_fraction = kelly_bet_fraction(equity, n_opponents, street)
    if bet_fraction == 0.0:
        return 0

    # FROM TARGETING: opponent-aware sizing
    if opp_is_loose and opp_aggression < 0.35:
        # Loose-passive — extract more value
        bet_fraction = min(bet_fraction * 1.10, MAX_BET_FRACTION)
    elif opp_aggression > 0.60:
        # Aggressive — control pot
        bet_fraction *= 0.88

    raise_size = int(pot * bet_fraction)
    raise_size = max(raise_size, min_raise_to)
    max_bet = your_stack + your_bet_this_street
    return min(raise_size, max_bet)


# ─────────────────────────────────────────────────────────
# SECTION 8: BLUFFING — Targeting's exploitation logic
# ─────────────────────────────────────────────────────────

BLUFF_FREQUENCY = 0.22   # FROM TARGETING — more aggressive baseline

def should_bluff(street, equity, n_opponents, opp_is_loose=False, opp_agg=0.5):
    """
    Bluff frequency adapts to opponent type:
      - Vs tight: +10% bluffs (they fold more)
      - Vs calling stations: never bluff
    """
    if n_opponents >= 3:
        return False
    if opp_is_loose:
        return False   # never bluff calling stations
    if street not in ("turn", "river"):
        return False
    if equity < 0.12:
        return False
    freq = BLUFF_FREQUENCY
    if opp_agg < 0.4:
        freq += 0.10   # +10% vs tight opponents
    return random.random() < freq


# ─────────────────────────────────────────────────────────
# SECTION 9: SHORT STACK / ALL-IN
# ─────────────────────────────────────────────────────────

def should_go_allin(your_stack, pot, equity, n_opponents=1):
    if your_stack <= 0:
        return False
    spr = your_stack / max(pot, 1)
    base_eq = 0.55 + (n_opponents - 1) * 0.05
    if spr <= 0.4 and equity >= base_eq:
        return True
    if spr <= 0.8 and equity >= base_eq + 0.10:
        return True
    return False


# ─────────────────────────────────────────────────────────
# SECTION 10: EQUITY THRESHOLDS
# ─────────────────────────────────────────────────────────

def get_thresholds(n_opponents):
    if n_opponents == 1:
        return 0.62, 0.28, 0.68
    elif n_opponents == 2:
        return 0.55, 0.32, 0.60
    elif n_opponents == 3:
        return 0.50, 0.36, 0.55
    elif n_opponents == 4:
        return 0.46, 0.38, 0.52
    else:
        return 0.43, 0.40, 0.50


# ─────────────────────────────────────────────────────────
# SECTION 11: OPPONENT RANGE STRENGTH (FROM RISK)
# ─────────────────────────────────────────────────────────

def estimate_opponent_range_strength(opp_seat, action_type, bet_size_pot_ratio):
    """
    Returns equity discount based on opponent type + action.
    Tight player raising = strong range = bigger discount.
    """
    profile = opponent_profiles.get(opp_seat, {})
    total_actions = profile.get("total_actions", 0)

    if total_actions < 5:
        if action_type == "large_bet":
            return 0.08
        if action_type == "raise":
            return 0.10
        return 0.0

    aggression, _ = get_opponent_stats(opp_seat)

    if aggression < 0.15:
        if action_type == "large_bet":
            return 0.18
        if action_type == "raise":
            return 0.25
        return 0.05
    if aggression > 0.50:
        if action_type == "large_bet":
            return 0.05
        if action_type == "raise":
            return 0.03
        return 0.0
    if action_type == "large_bet":
        return 0.10
    if action_type == "raise":
        return 0.12
    return 0.0


# ─────────────────────────────────────────────────────────
# SECTION 12: MAIN DECIDE FUNCTION
# ─────────────────────────────────────────────────────────

def decide(game_state: dict) -> dict:
    hole_cards            = game_state.get("your_cards", [])
    community_cards       = game_state.get("community_cards", [])
    street                = game_state.get("street", "preflop")
    pot                   = game_state.get("pot", 0)
    your_stack            = game_state.get("your_stack", 0)
    your_bet_this_street  = game_state.get("your_bet_this_street", 0)
    amount_owed           = game_state.get("amount_owed", 0)
    can_check             = game_state.get("can_check", False)
    min_raise_to          = game_state.get("min_raise_to", 0)
    players               = game_state.get("players", [])
    action_log            = game_state.get("action_log", [])

    if not hole_cards:
        return {"action": "fold"}

    my_seat     = get_my_seat(game_state)
    n_opponents = count_active_opponents(players, my_seat)
    n_players   = max(len(players), n_opponents + 1)
    position    = get_position(my_seat, n_players)
    in_pos      = is_in_position(position)

    try:
        update_opponent_models(action_log, my_seat)
    except Exception:
        pass

    opp_seat = primary_opponent_seat(players, my_seat)
    opp_agg, opp_loose = get_opponent_stats(opp_seat) if opp_seat else (0.5, False)

    # ─────────────────────────────────────────────────────
    # PREFLOP
    # ─────────────────────────────────────────────────────
    if street == "preflop":
        pf_eq = lookup_preflop_equity(hole_cards, n_opponents)
        if pf_eq is None:
            pf_eq = evaluate_preflop_strength(hole_cards, n_opponents)

        # ── FROM RISK: Opponent-aware preflop discount ───
        # Critical for avoiding 3-bet/4-bet disasters
        preflop_raises = sum(1 for a in action_log
            if a.get("street") == "preflop"
            and a.get("action") in ("raise", "all_in"))

        last_raiser = None
        for a in reversed(action_log):
            if (a.get("street") == "preflop"
                and a.get("action") in ("raise", "all_in")
                and a.get("seat") != my_seat):
                last_raiser = a.get("seat")
                break

        opp_discount = 0.0
        if last_raiser is not None:
            profile = opponent_profiles.get(last_raiser, {})
            total = profile.get("total_actions", 0)
            if total >= 10:
                agg = profile.get("aggressive_actions", 0) / total
                if agg < 0.15:
                    opp_discount = 0.20
                elif agg > 0.50:
                    opp_discount = 0.03
                else:
                    opp_discount = 0.10
            else:
                opp_discount = 0.08

        if preflop_raises >= 2:
            pf_eq -= max(0.15, opp_discount + 0.05)
        elif preflop_raises >= 1 and amount_owed > 0:
            pf_eq -= opp_discount

        pos_loosen = 0.04 if in_pos else 0.0
        if n_opponents == 1:
            raise_thresh, call_thresh = 0.62 - pos_loosen, 0.48 - pos_loosen
        elif n_opponents == 2:
            raise_thresh, call_thresh = 0.55 - pos_loosen, 0.43 - pos_loosen
        elif n_opponents == 3:
            raise_thresh, call_thresh = 0.48 - pos_loosen, 0.38 - pos_loosen
        else:
            raise_thresh, call_thresh = 0.44 - pos_loosen, 0.35 - pos_loosen

        # ── FROM RISK: Preflop commitment cap ────────────
        # If calling/raising would commit > 30% of stack without
        # a premium hand (eq > 0.70), fold. Prevents 3-bet/4-bet
        # disasters with JJ/AK against AA/KK.
        starting_stack_pf = your_stack + your_bet_this_street
        new_commit_pf = (your_bet_this_street + amount_owed) / max(starting_stack_pf, 1)
        if new_commit_pf > 0.30 and pf_eq < 0.70 and amount_owed > 0:
            return {"action": "fold"}

        if can_check:
            if pf_eq >= raise_thresh:
                amt = calculate_raise_amount(pot, pf_eq, min_raise_to, your_stack,
                                              your_bet_this_street,
                                              n_opponents, opp_agg, opp_loose,
                                              street=street)
                if amt > 0:
                    return {"action": "raise", "amount": amt}
            return {"action": "check"}

        if pf_eq >= raise_thresh:
            amt = calculate_raise_amount(pot, pf_eq, min_raise_to, your_stack,
                                          your_bet_this_street,
                                          n_opponents, opp_agg, opp_loose,
                                          street=street)
            if amt > 0:
                return {"action": "raise", "amount": amt}
            return {"action": "call"}

        if pf_eq >= call_thresh:
            pot_odds = calculate_pot_odds(pot, amount_owed)
            adjusted_thresh = call_thresh + (0.04 if opp_agg > 0.55 else 0.0)
            if pf_eq > max(pot_odds, adjusted_thresh - 0.15):
                return {"action": "call"}

        return {"action": "fold"}

    # ─────────────────────────────────────────────────────
    # POST-FLOP
    # ─────────────────────────────────────────────────────
    else:
        equity = calculate_equity(hole_cards, community_cards,
                                   n_opponents=n_opponents, n_sims=1000)

        # Save raw equity for bluff decision (don't discount our bluff equity)
        raw_equity = equity

        # ── FROM RISK: Range-aware opponent discount ─────
        recent_action = None
        recent_actor  = None
        recent_amount = 0
        for action in reversed(action_log):
            if action.get("seat") != my_seat:
                recent_action = action.get("action")
                recent_actor  = action.get("seat")
                recent_amount = action.get("amount", 0)
                break

        opp_discount = 0.0
        if recent_actor is not None and recent_action in ("raise", "all_in", "bet"):
            bet_ratio = recent_amount / max(pot, 1)
            action_type = "large_bet" if bet_ratio > 0.6 else "raise"
            opp_discount = estimate_opponent_range_strength(
                recent_actor, action_type, bet_ratio
            )

        # Multi-way discount
        multiway_discount = 0.0
        if n_opponents >= 3:
            multiway_discount = 0.04 + (n_opponents - 3) * 0.02

        # Apply LARGER of the two — don't stack (FROM RISK)
        final_discount = max(opp_discount, multiway_discount)
        equity = max(0.0, equity - final_discount)

        pot_odds_req = calculate_pot_odds(pot, amount_owed)
        pos_bonus = 0.02 if in_pos else 0.0
        eff_equity = equity + pos_bonus

        value_eq, call_floor, raise_for_value = get_thresholds(n_opponents)

        # ── FROM RISK: Post-flop commitment cap ──────────
        starting_stack = your_stack + your_bet_this_street
        already_committed = your_bet_this_street
        if equity >= 0.80:
            max_commit = 0.50
        elif equity >= 0.65:
            max_commit = 0.35
        else:
            max_commit = 0.25
        new_commit = (already_committed + amount_owed) / max(starting_stack, 1)
        if new_commit > max_commit and amount_owed > 0 and not can_check:
            if equity < 0.75:
                return {"action": "fold"}

        # ── All-in check ─────────────────────────────────
        if should_go_allin(your_stack, pot, equity, n_opponents):
            return {"action": "all_in"}

        if amount_owed >= your_stack > 0:
            allin_threshold = 0.55 + (n_opponents - 1) * 0.05
            if equity >= allin_threshold:
                return {"action": "all_in"}
            return {"action": "fold"}

        # ── Free check ───────────────────────────────────
        if can_check:
            if eff_equity >= value_eq:
                amt = calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                                              your_bet_this_street,
                                              n_opponents, opp_agg, opp_loose,
                                              street=street)
                if amt > 0:
                    return {"action": "raise", "amount": amt}
            return {"action": "check"}

        # ── Strong hand: raise for value ─────────────────
        if eff_equity >= raise_for_value:
            amt = calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                                          your_bet_this_street,
                                          n_opponents, opp_agg, opp_loose,
                                          street=street)
            if amt > 0:
                return {"action": "raise", "amount": amt}
            return {"action": "call"}

        # ── Decent hand: call if equity beats pot odds ────
        # (TARGETING uses no margin — beats pot odds is enough)
        if eff_equity > pot_odds_req and equity >= call_floor:
            if eff_equity >= (raise_for_value - 0.08):
                amt = calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                                              your_bet_this_street,
                                              n_opponents, opp_agg, opp_loose,
                                              street=street)
                if amt > 0:
                    return {"action": "raise", "amount": amt}
            return {"action": "call"}

        # ── Bluff (TARGETING'S aggressive bluffing) ──────
        # Use raw_equity (not discounted) — bluffs are about fold equity,
        # not about beating opponent's range when called.
        if should_bluff(street, raw_equity, n_opponents, opp_loose, opp_agg):
            bsz = max(int(pot * 0.50), min_raise_to)
            bsz = min(bsz, your_stack + your_bet_this_street)
            if bsz > 0:
                return {"action": "raise", "amount": bsz}

        return {"action": "fold"}


# ─────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    def make_state(**kwargs):
        defaults = {
            "your_cards": [], "community_cards": [],
            "street": "preflop", "pot": 0, "your_stack": 5000,
            "your_bet_this_street": 0,
            "amount_owed": 0, "can_check": True, "current_bet": 0,
            "min_raise_to": 100, "players": [], "action_log": [],
            "seat_to_act": 0,
        }
        defaults.update(kwargs)
        return defaults

    tests = [
        {"name": "AK on A-7-2 flop, heads-up, facing bet → RAISE",
         "expect": "raise",
         "state": make_state(
             your_cards=["As","Ks"], community_cards=["Ah","7d","2c"],
             street="flop", pot=1200, your_stack=8000,
             amount_owed=300, can_check=False, current_bet=300,
             min_raise_to=600,
             players=[{"stack":8000},{"stack":8000}], seat_to_act=0)},
        {"name": "AK on A-7-2 flop, 5-way pot, facing bet → CALL or RAISE",
         "expect": ["call","raise"],
         "state": make_state(
             your_cards=["As","Ks"], community_cards=["Ah","7d","2c"],
             street="flop", pot=2000, your_stack=8000,
             amount_owed=300, can_check=False, current_bet=300,
             min_raise_to=600,
             players=[{"stack":5000} for _ in range(6)], seat_to_act=2)},
        {"name": "2-7 offsuit preflop, facing bet → FOLD",
         "expect": "fold",
         "state": make_state(
             your_cards=["2s","7d"],
             street="preflop", pot=150, your_stack=5000,
             amount_owed=100, can_check=False, current_bet=100,
             min_raise_to=200,
             players=[{"stack":5000},{"stack":5000}], seat_to_act=1)},
        {"name": "AA preflop, can_check=True → RAISE",
         "expect": "raise",
         "state": make_state(
             your_cards=["Ac","Ad"],
             street="preflop", pot=150, your_stack=5000,
             amount_owed=0, can_check=True, min_raise_to=100,
             players=[{"stack":5000},{"stack":5000}], seat_to_act=0)},
        {"name": "Short stack: AK on A72, stack=200, owed=500 → ALL-IN",
         "expect": "all_in",
         "state": make_state(
             your_cards=["As","Ks"], community_cards=["Ah","7d","2c"],
             street="flop", pot=2000, your_stack=200,
             amount_owed=500, can_check=False, current_bet=500,
             min_raise_to=1000,
             players=[{"stack":200},{"stack":5000}], seat_to_act=0)},
        {"name": "AK on AK2 (two pair), can_check=True → RAISE",
         "expect": "raise",
         "state": make_state(
             your_cards=["As","Ks"], community_cards=["Ah","Kd","2c"],
             street="flop", pot=1000, your_stack=8000,
             amount_owed=0, can_check=True, min_raise_to=100,
             players=[{"stack":8000},{"stack":8000}], seat_to_act=1)},
        {"name": "27o multiway (5 opp), can_check → CHECK",
         "expect": "check",
         "state": make_state(
             your_cards=["2s","7h"], community_cards=["Td","Jc","Qh"],
             street="flop", pot=500, your_stack=4000,
             amount_owed=0, can_check=True, min_raise_to=100,
             players=[{"stack":4000} for _ in range(6)], seat_to_act=0)},
    ]

    print("=" * 65)
    print("SELF-TEST — Targeting + Discipline hybrid")
    print("=" * 65)
    passed = 0
    for t in tests:
        t0 = time.time()
        result = decide(t["state"])
        ms = (time.time() - t0) * 1000
        action = result["action"]
        expected = t["expect"]
        ok = action in expected if isinstance(expected, list) else action == expected
        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        n_opp = count_active_opponents(t["state"]["players"],
                                        get_my_seat(t["state"]))
        print(f"  [{status}] {t['name']}")
        print(f"         n_opp={n_opp}  ->  {result}  ({ms:.0f}ms)")

    print(f"\n  {passed}/{len(tests)} tests passed\n")