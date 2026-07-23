"""
PERSONALITY 2: LOOSE-AGGRESSIVE (LAG, one-file bot)
====================================================
Strategy: Wider preflop ranges, more bluffs, smaller bets often.
Plays ~30% of hands. Bluffs 32% on turn/river. Targets shark-style
tight bots by attacking with relentless aggression.

High variance but exploits tight opponents who fold too much.
"""

import eval7
import random

# ─────────────────────────────────────────────────────────
# PRECOMPUTED PREFLOP EQUITY TABLE
#
# Keyed by (rank1, rank2, suited, n_opponents).
# Generated offline from 2000 Monte Carlo sims per entry.
# Loaded once at module import — zero cost inside decide().
#
# Rather than shipping a data/ file, we hardcode the most
# important entries as a dict. Anything not in the table
# falls back to evaluate_preflop_strength().
# ─────────────────────────────────────────────────────────

# Format: (high_rank, low_rank, is_suited) -> [eq_vs1, eq_vs2, eq_vs3, eq_vs4, eq_vs5]
# Ranks: A=14, K=13, Q=12, J=11, T=10, 9=9, 8=8, 7=7, 6=6, 5=5, 4=4, 3=3, 2=2
PREFLOP_EQ_TABLE = {
    # Pocket pairs
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
    # AK
    (14,13,True):  [0.670,0.502,0.398,0.329,0.282],
    (14,13,False): [0.641,0.467,0.365,0.299,0.254],
    # AQ
    (14,12,True):  [0.659,0.487,0.382,0.314,0.268],
    (14,12,False): [0.628,0.449,0.348,0.283,0.240],
    # AJ
    (14,11,True):  [0.647,0.471,0.366,0.299,0.253],
    (14,11,False): [0.615,0.431,0.331,0.267,0.225],
    # AT
    (14,10,True):  [0.635,0.453,0.350,0.284,0.239],
    (14,10,False): [0.602,0.414,0.315,0.253,0.212],
    # A9-A2 suited
    (14,9,True):   [0.607,0.421,0.320,0.257,0.215],
    (14,8,True):   [0.592,0.403,0.303,0.241,0.201],
    (14,7,True):   [0.580,0.388,0.289,0.229,0.190],
    (14,6,True):   [0.568,0.375,0.277,0.218,0.180],
    (14,5,True):   [0.560,0.366,0.268,0.210,0.172],
    # KQ
    (13,12,True):  [0.631,0.462,0.357,0.290,0.245],
    (13,12,False): [0.599,0.423,0.321,0.258,0.216],
    # KJ
    (13,11,True):  [0.619,0.444,0.340,0.274,0.230],
    (13,11,False): [0.585,0.404,0.305,0.243,0.203],
    # KT
    (13,10,True):  [0.607,0.428,0.324,0.259,0.216],
    (13,10,False): [0.571,0.386,0.289,0.229,0.190],
    # QJ
    (12,11,True):  [0.607,0.430,0.326,0.261,0.218],
    (12,11,False): [0.572,0.390,0.291,0.230,0.191],
    # QT
    (12,10,True):  [0.596,0.413,0.310,0.246,0.204],
    (12,10,False): [0.558,0.371,0.274,0.216,0.178],
    # JT
    (11,10,True):  [0.577,0.396,0.296,0.233,0.193],
    (11,10,False): [0.539,0.353,0.259,0.202,0.166],
    # T9
    (10,9,True):   [0.557,0.375,0.277,0.218,0.179],
    (10,9,False):  [0.517,0.332,0.241,0.187,0.153],
    # 98
    (9,8,True):    [0.539,0.355,0.260,0.202,0.165],
    (9,8,False):   [0.497,0.311,0.223,0.172,0.140],
    # 87
    (8,7,True):    [0.521,0.337,0.243,0.188,0.153],
    (8,7,False):   [0.478,0.292,0.207,0.159,0.128],
}


def lookup_preflop_equity(hole_cards, n_opponents):
    """
    Look up preflop equity from the hardcoded table.
    Returns None if not found (caller falls back to scoring function).
    n_opponents: number of opponents still in the hand (1–5).
    """
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

    idx = min(n_opponents - 1, 4)   # clamp to table range (vs1–vs5)
    return row[idx]


# ─────────────────────────────────────────────────────────
# SECTION 1: CARD UTILITIES
# ─────────────────────────────────────────────────────────

def rank_value(rank):
    return {"A":14,"K":13,"Q":12,"J":11,"T":10,
            "9":9,"8":8,"7":7,"6":6,"5":5,"4":4,"3":3,"2":2}.get(rank, 0)


# ─────────────────────────────────────────────────────────
# SECTION 2: PREFLOP FALLBACK SCORER
#
# Used only for hands not in the precomputed table above.
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

    # Scale down for more opponents: each extra opponent reduces equity
    # Empirically: equity_vs_n ≈ equity_vs_1 * (0.82 ^ (n-1))
    scale = 0.82 ** (n_opponents - 1)
    return base * scale


# ─────────────────────────────────────────────────────────
# SECTION 3: MULTI-OPPONENT EQUITY (Monte Carlo)
#
# FIX: Simulates all active opponents, not just one.
# On a 6-player table with 5 active opponents, AK on A72
# has ~56% equity, not 89%. This is the most impactful fix.
#
# eval7.evaluate() — HIGHER score = BETTER hand.
# ─────────────────────────────────────────────────────────

def calculate_equity(hole_cards, community_cards, n_opponents=1, n_sims=1000):
    """
    Estimate win probability vs n_opponents via Monte Carlo.

    n_opponents: number of active opponents (not folded, not us).
                 Clamped to 1–5.
    """
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

            # Deal each opponent 2 cards
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
        return 1.0 / (n_opponents + 1)   # uniform fallback


# ─────────────────────────────────────────────────────────
# SECTION 4: POT ODDS
# ─────────────────────────────────────────────────────────

def calculate_pot_odds(pot, amount_owed):
    if amount_owed <= 0:
        return 0.0
    return amount_owed / (pot + amount_owed)


# ─────────────────────────────────────────────────────────
# SECTION 5: ACTIVE OPPONENT COUNTING
#
# Counts how many opponents are still live (not folded).
# Uses players list — tries multiple field name formats
# since the README only says "public info on all seats".
# ─────────────────────────────────────────────────────────

def count_active_opponents(players, my_seat):
    """
    Return the number of opponents still in the hand (excluding ourselves).

    Default: len(players) - 1 gives total opponents at the table.
    If we can detect fold status, subtract folded opponents.

    NOTE: the engine's 'players' list may not include a 'seat' field on each
    dict. We fall back to list index in that case.
    """
    if not players:
        return 1   # safe fallback for unit tests

    total_opponents = len(players) - 1
    if total_opponents <= 0:
        return 1

    folded_count = 0
    for i, p in enumerate(players):
        # Use 'seat' field if present, else list index
        seat = p.get("seat", i) if isinstance(p, dict) else i
        if seat == my_seat:
            continue
        if isinstance(p, dict):
            folded = (p.get("folded") or p.get("is_folded") or
                      p.get("out") or p.get("status") == "folded")
            stack  = p.get("stack", 1)
            if folded or stack <= 0:
                folded_count += 1

    active = total_opponents - folded_count
    return max(1, active)


def get_my_seat(game_state):
    """
    Extract our own seat number.
    The engine passes 'seat_to_act' (the seat whose turn it is).
    Since decide() is only called when it IS our turn, seat_to_act == us.
    """
    return game_state.get("seat_to_act", 0)


def get_position(seat_to_act, n_players):
    """
    Return position as a 0.0 (early) to 1.0 (late) float.
    Late position = closer to the button = more information advantage.
    """
    if n_players <= 1:
        return 0.5
    return seat_to_act / max(n_players - 1, 1)


# ─────────────────────────────────────────────────────────
# SECTION 6: OPPONENT MODELLING
#
# Tracks per-seat stats across 400 hands.
# Reliable profiles emerge by hand ~25–30.
# Stats used: aggression_ratio, VPIP (loose/tight).
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
    """Returns (aggression 0-1, is_loose bool). Defaults if < 15 samples."""
    p = opponent_profiles.get(seat)
    if not p or p["total_actions"] < 15:
        return 0.50, False
    agg   = p["aggressive_actions"] / p["total_actions"]
    vpip  = p["voluntary_entries"] / max(p["hands_seen"], 1)
    return agg, vpip > 0.35


def primary_opponent_seat(players, my_seat):
    best, best_n = None, 0
    for seat, p in opponent_profiles.items():
        if seat != my_seat and p["total_actions"] > best_n:
            best, best_n = seat, p["total_actions"]
    return best


# ─────────────────────────────────────────────────────────
# SECTION 7: BET SIZING — KELLY CRITERION
#
# The Kelly criterion answers: "given my edge, what fraction of
# my bankroll should I bet?" The classic formula is:
#
#     f* = (b*p - q) / b
#
# where:
#   f* = optimal fraction of stack to bet
#   p  = probability we win (our equity)
#   q  = 1 - p (probability we lose)
#   b  = odds offered (pot won / amount risked)
#
# Practical adaptations for poker:
#
# 1. EDGE UNCERTAINTY: Monte Carlo equity is accurate to ±1.5%.
#    We subtract a safety margin from p before computing f*.
#    Better to under-bet than over-bet on noisy estimates.
#
# 2. FRACTIONAL KELLY: pure Kelly is too aggressive when:
#      - p is uncertain (poker)
#      - opponent might fold (no realization of equity)
#      - tournament variance matters more than long-run EV
#    We use HALF-Kelly (multiply f* by 0.5) for safety.
#
# 3. POT-FRACTION CONVERSION: Kelly gives "fraction of stack".
#    But raise amounts are usually framed as fraction of pot.
#    We use the resulting EV-optimal bet size in pot-fractions.
#
# 4. MULTI-WAY ADJUSTMENT: more opponents = lower effective equity
#    (already baked into p), and smaller fold equity. Reduce bet
#    fraction by 15% in multi-way pots.
# ─────────────────────────────────────────────────────────

# Kelly tuning constants
KELLY_FRACTION = 0.70   # LAG: smaller more-frequent bets     # 0.85 = strong Kelly (not full, to handle eq noise)
EDGE_UNCERTAINTY = 0.03   # subtract from p before Kelly calc
MIN_BET_FRACTION = 0.40   # don't bet less than 40% pot (gives bad odds)
MAX_BET_FRACTION = 1.00   # don't overbet beyond pot

def kelly_bet_fraction(equity, n_opponents=1):
    """
    Returns the fraction of pot to bet using Kelly criterion.
    Returns 0 if no edge.

    The simplification: we assume opponent calls with random hands
    that have approximately our pot odds in equity. Under this
    assumption, the EV-optimal bet (full Kelly) is:

        f_pot = (2p - 1) / (1 - p)    [pot-relative]

    For values near p=0.6, this gives f_pot ≈ 0.5 (half-pot)
    For p=0.7, f_pot ≈ 1.33 (overbet)
    For p=0.8, f_pot ≈ 3.0 (massive overbet — capped)

    We multiply by KELLY_FRACTION = 0.70   # LAG: smaller more-frequent bets to dampen the overbets.
    """
    # Account for uncertainty in equity estimate (MC variance, range awareness)
    p = equity - EDGE_UNCERTAINTY
    if p <= 0.5:
        return 0.0   # no edge → don't bet

    # Pot-relative Kelly for symmetric bet (opponent calls with even odds)
    # f_pot = (2p - 1) / (1 - p), then dampen by KELLY_FRACTION
    raw_fraction = (2.0 * p - 1.0) / (1.0 - p)
    bet_fraction = raw_fraction * KELLY_FRACTION

    # Multi-way adjustment: less fold equity, smaller bets
    if n_opponents >= 3:
        bet_fraction *= 0.85
    elif n_opponents == 2:
        bet_fraction *= 0.92

    # Clamp to reasonable bounds
    bet_fraction = max(MIN_BET_FRACTION, min(bet_fraction, MAX_BET_FRACTION))
    return bet_fraction


def calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                            your_bet_this_street=0,
                            n_opponents=1, opp_aggression=0.5, opp_is_loose=False):
    """
    Compute optimal raise amount using Kelly criterion.

    Returns TOTAL bet target (not additional chips), respecting:
      - min_raise_to: legal minimum
      - your_stack + your_bet_this_street: maximum legal target
    """
    # Get Kelly-optimal bet fraction of pot
    bet_fraction = kelly_bet_fraction(equity, n_opponents)

    if bet_fraction == 0.0:
        return 0   # no edge → don't bet

    # Adjust for opponent type (small modifications to Kelly output)
    if opp_is_loose and opp_aggression < 0.35:
        # Loose-passive opponents call too much → extract more value
        bet_fraction = min(bet_fraction * 1.10, MAX_BET_FRACTION)
    elif opp_aggression > 0.60:
        # Aggressive opponents may re-raise → bet smaller to control pot
        bet_fraction *= 0.88

    # Convert pot fraction to chip amount
    raise_size = int(pot * bet_fraction)
    raise_size = max(raise_size, min_raise_to)

    # CAP: total bet target can't exceed stack + already_committed_this_street
    max_bet = your_stack + your_bet_this_street
    raise_size = min(raise_size, max_bet)
    return raise_size


# ─────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────
# SECTION 8: BLUFFING
#
# Never bluff into multi-way pots (3+ opponents).
# With 3 players seeing the flop, someone almost always
# has a piece of the board — bluffs fail and drain chips.
# ─────────────────────────────────────────────────────────

BLUFF_FREQUENCY = 0.32   # LAG: bluff often

def should_bluff(street, equity, n_opponents):
    if n_opponents >= 3:
        return False   # never bluff multi-way
    if street not in ("turn", "river"):
        return False
    if equity < 0.08:   # LAG: bluff thinner
        return False
    return random.random() < BLUFF_FREQUENCY


# ─────────────────────────────────────────────────────────
# SECTION 9: SHORT STACK / ALL-IN
# ─────────────────────────────────────────────────────────

def should_go_allin(your_stack, pot, equity, n_opponents=1):
    """
    Going all-in commits 100% of your remaining chips. The bar must be high
    or you lose your whole stack to suckouts. Tightened thresholds:
      - Used to fire at SPR<=0.5 with eq>=0.38 → busted often
      - Now requires SPR<=0.4 AND eq>=0.55 heads-up (much stricter)
    """
    if your_stack <= 0:
        return False
    spr = your_stack / max(pot, 1)

    # Heads-up: need 55%+ equity to go all-in even when committed
    # Multi-way: need even higher (more opponents = more ways to lose)
    base_eq = 0.55 + (n_opponents - 1) * 0.05

    if spr <= 0.4 and equity >= base_eq:
        return True
    if spr <= 0.8 and equity >= base_eq + 0.10:
        return True
    return False


# ─────────────────────────────────────────────────────────
# SECTION 10: POSITION DETECTION
#
# Position is a continuous 0.0 (early) to 1.0 (late) value
# derived from seat_to_act / (n_players - 1).
# Late = closer to dealer button = more information.
# Matches shark's approach: position = seat / (n - 1)
# ─────────────────────────────────────────────────────────

def is_in_position(position_float):
    """Position > 0.5 = late position (we have info advantage)."""
    return position_float > 0.5


# ─────────────────────────────────────────────────────────
# SECTION 11: EQUITY THRESHOLDS BY OPPONENT COUNT
#
# How strong you need to be to value-bet or call depends
# heavily on how many people are contesting the pot.
# ─────────────────────────────────────────────────────────

def get_thresholds(n_opponents):
    """
    LAG: looser call floor, lower value-raise threshold.
    Returns (value_raise_eq, call_floor, raise_for_value_eq).
    """
    if n_opponents == 1:
        return 0.56, 0.25, 0.62
    elif n_opponents == 2:
        return 0.50, 0.30, 0.55
    elif n_opponents == 3:
        return 0.45, 0.34, 0.50
    elif n_opponents == 4:
        return 0.42, 0.38, 0.48
    else:  # 5+
        return 0.40, 0.40, 0.46


# ─────────────────────────────────────────────────────────
# SECTION 12: MAIN DECIDE FUNCTION
# ─────────────────────────────────────────────────────────

def decide(game_state: dict) -> dict:
    """
    Called once per action. Must return within 2 seconds.

    Fields used (confirmed from reference shark bot source):
      your_cards, community_cards, street, pot, your_stack,
      your_bet_this_street, amount_owed, can_check, min_raise_to,
      players, seat_to_act, action_log
    """
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

    # ── Safety guards ────────────────────────────────────
    if not hole_cards:
        return {"action": "fold"}

    # ── Derive seat, opponent count, position ────────────
    my_seat     = get_my_seat(game_state)
    n_opponents = count_active_opponents(players, my_seat)
    n_players   = max(len(players), n_opponents + 1)
    position    = get_position(my_seat, n_players)   # 0.0 early, 1.0 late
    in_pos      = is_in_position(position)

    # ── Update opponent models ───────────────────────────
    try:
        update_opponent_models(action_log, my_seat)
    except Exception:
        pass

    # ── Get opponent profile ─────────────────────────────
    opp_seat = primary_opponent_seat(players, my_seat)
    opp_agg, opp_loose = get_opponent_stats(opp_seat) if opp_seat else (0.5, False)

    # ─────────────────────────────────────────────────────
    # PREFLOP
    # ─────────────────────────────────────────────────────
    if street == "preflop":
        # Use precomputed table first, fallback to scorer
        pf_eq = lookup_preflop_equity(hole_cards, n_opponents)
        if pf_eq is None:
            pf_eq = evaluate_preflop_strength(hole_cards, n_opponents)

        # Position-aware thresholds: looser in late position
        pos_loosen = 0.04 if in_pos else 0.0

        # LAG: loosened thresholds (play more hands)
        if n_opponents == 1:
            raise_thresh, call_thresh = 0.58 - pos_loosen, 0.44 - pos_loosen
        elif n_opponents == 2:
            raise_thresh, call_thresh = 0.51 - pos_loosen, 0.40 - pos_loosen
        elif n_opponents == 3:
            raise_thresh, call_thresh = 0.45 - pos_loosen, 0.35 - pos_loosen
        else:
            raise_thresh, call_thresh = 0.42 - pos_loosen, 0.32 - pos_loosen

        if can_check:
            if pf_eq >= raise_thresh:
                amt = calculate_raise_amount(pot, pf_eq, min_raise_to, your_stack,
                                              your_bet_this_street,
                                              n_opponents, opp_agg, opp_loose)
                if amt > 0:
                    return {"action": "raise", "amount": amt}
            return {"action": "check"}   # can_check=True so this is always valid

        # Facing a bet preflop
        if pf_eq >= raise_thresh:
            amt = calculate_raise_amount(pot, pf_eq, min_raise_to, your_stack,
                                          your_bet_this_street,
                                          n_opponents, opp_agg, opp_loose)
            if amt > 0:
                return {"action": "raise", "amount": amt}
            return {"action": "call"}

        if pf_eq >= call_thresh:
            pot_odds = calculate_pot_odds(pot, amount_owed)
            # Tighten vs aggressive opponents (their range is stronger)
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
        pot_odds_req = calculate_pot_odds(pot, amount_owed)

        pos_bonus = 0.04 if in_pos else 0.0   # LAG: bigger position bonus
        eff_equity = equity + pos_bonus

        value_eq, call_floor, raise_for_value = get_thresholds(n_opponents)

        # ── All-in check ─────────────────────────────────
        if should_go_allin(your_stack, pot, equity, n_opponents):
            return {"action": "all_in"}

        if amount_owed >= your_stack > 0:
            # Forced all-in: tightened threshold to avoid catastrophic losses
            allin_threshold = 0.55 + (n_opponents - 1) * 0.05
            if equity >= allin_threshold:
                return {"action": "all_in"}
            return {"action": "fold"}

        # ── Free check ───────────────────────────────────
        if can_check:
            if eff_equity >= value_eq:
                amt = calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                                              your_bet_this_street,
                                              n_opponents, opp_agg, opp_loose)
                if amt > 0:
                    return {"action": "raise", "amount": amt}
            return {"action": "check"}

        # ── Strong hand: raise for value ─────────────────
        if eff_equity >= raise_for_value:
            amt = calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                                          your_bet_this_street,
                                          n_opponents, opp_agg, opp_loose)
            if amt > 0:
                return {"action": "raise", "amount": amt}
            return {"action": "call"}

        # ── Decent hand: call if equity beats pot odds ────
        if eff_equity > pot_odds_req and equity >= call_floor:
            if eff_equity >= (raise_for_value - 0.08):
                amt = calculate_raise_amount(pot, equity, min_raise_to, your_stack,
                                              your_bet_this_street,
                                              n_opponents, opp_agg, opp_loose)
                if amt > 0:
                    return {"action": "raise", "amount": amt}
            return {"action": "call"}

        # ── Bluff (heads-up or 2-way only) ───────────────
        if should_bluff(street, equity, n_opponents):
            bsz = max(int(pot * 0.50), min_raise_to)
            bsz = min(bsz, your_stack + your_bet_this_street)
            if bsz > 0:
                return {"action": "raise", "amount": bsz}

        return {"action": "fold"}


# ─────────────────────────────────────────────────────────
# SELF-TEST
# python3 bots/mybot/bot.py
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    # Helper to build a complete state dict for tests
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
        {
            "name": "AK on A-7-2 flop, heads-up, facing bet → RAISE",
            "expect": "raise",
            "state": make_state(
                your_cards=["As","Ks"], community_cards=["Ah","7d","2c"],
                street="flop", pot=1200, your_stack=8000,
                amount_owed=300, can_check=False, current_bet=300,
                min_raise_to=600,
                players=[{"stack":8000},{"stack":8000}],
                seat_to_act=0,
            )
        },
        {
            "name": "AK on A-7-2 flop, 5-way pot, facing bet → CALL or RAISE",
            "expect": ["call","raise"],
            "state": make_state(
                your_cards=["As","Ks"], community_cards=["Ah","7d","2c"],
                street="flop", pot=2000, your_stack=8000,
                amount_owed=300, can_check=False, current_bet=300,
                min_raise_to=600,
                players=[{"stack":5000} for _ in range(6)],
                seat_to_act=2,
            )
        },
        {
            "name": "2-7 offsuit preflop, facing bet → FOLD",
            "expect": "fold",
            "state": make_state(
                your_cards=["2s","7d"],
                street="preflop", pot=150, your_stack=5000,
                amount_owed=100, can_check=False, current_bet=100,
                min_raise_to=200,
                players=[{"stack":5000},{"stack":5000}],
                seat_to_act=1,
            )
        },
        {
            "name": "AA preflop, can_check=True → RAISE",
            "expect": "raise",
            "state": make_state(
                your_cards=["Ac","Ad"],
                street="preflop", pot=150, your_stack=5000,
                amount_owed=0, can_check=True,
                min_raise_to=100,
                players=[{"stack":5000},{"stack":5000}],
                seat_to_act=0,
            )
        },
        {
            "name": "Short stack: AK on A72, stack=200, owed=500 → ALL-IN",
            "expect": "all_in",
            "state": make_state(
                your_cards=["As","Ks"], community_cards=["Ah","7d","2c"],
                street="flop", pot=2000, your_stack=200,
                amount_owed=500, can_check=False, current_bet=500,
                min_raise_to=1000,
                players=[{"stack":200},{"stack":5000}],
                seat_to_act=0,
            )
        },
        {
            "name": "AK on AK2 board (two pair), can_check=True → RAISE",
            "expect": "raise",
            "state": make_state(
                your_cards=["As","Ks"], community_cards=["Ah","Kd","2c"],
                street="flop", pot=1000, your_stack=8000,
                amount_owed=0, can_check=True,
                min_raise_to=100,
                players=[{"stack":8000},{"stack":8000}],
                seat_to_act=1,
            )
        },
        {
            "name": "27o multiway (5 opponents), can_check=True → CHECK (no bluff)",
            "expect": "check",
            "state": make_state(
                your_cards=["2s","7h"], community_cards=["Td","Jc","Qh"],
                street="flop", pot=500, your_stack=4000,
                amount_owed=0, can_check=True,
                min_raise_to=100,
                players=[{"stack":4000} for _ in range(6)],
                seat_to_act=0,
            )
        },
    ]

    print("=" * 65)
    print("SELF-TEST — bot.py v3 (real engine field names)")
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

    print("Speed benchmark:")
    t0 = time.time()
    for _ in range(15):
        calculate_equity(["As","Ks"], ["Ah","7d","2c"], n_opponents=5, n_sims=1000)
    avg = (time.time()-t0)/15*1000
    print(f"  1000 sims vs 5 opponents: {avg:.0f}ms avg  ({'OK' if avg < 400 else 'SLOW'})")