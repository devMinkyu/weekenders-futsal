#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import itertools
import random
from collections import defaultdict

from grades import PLAYER_ABILITIES, MERCENARY_GRADE, player_score, ABILITY_KEYS
from members import MEMBERS
from positions import PLAYER_POSITIONS, IDEAL_POSITIONS, IDEAL_POSITIONS_5, IDEAL_POSITIONS_6, IDEAL_POSITIONS_7


# ─────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────

def is_mercenary(name):
    return name not in PLAYER_ABILITIES


class NotEnoughPlayersError(Exception):
    """인원이 모자라 팀을 구성할 수 없음."""


class AmbiguousNameError(Exception):
    """이름(성 제외)만으로 매칭 시 후보가 2명 이상이라 특정 불가."""
    def __init__(self, input_name, candidates):
        self.input_name = input_name
        self.candidates = candidates
        super().__init__(
            f"'{input_name}' 은(는) 여러 명과 일치해요: {', '.join(candidates)}\n"
            f"→ 성을 붙여서 정확히 입력해주세요."
        )


def resolve_name(input_name, registered_names=None):
    """
    참석자 이름을 등록명으로 보정한다.
      1) 완전일치 → 그대로
      2) 등록명이 입력값으로 끝남(endswith) 매칭 1명 → 그 등록명
      3) 매칭 2명 이상 → AmbiguousNameError (모호)
      4) 매칭 0명 → 입력값 그대로 (용병/미등록 처리)
    """
    if registered_names is None:
        registered_names = list(PLAYER_ABILITIES.keys())
    name = input_name.strip()
    if name in registered_names:          # 1) 완전일치 우선
        return name
    # 2~3) 성 제외 매칭: 등록명이 입력값으로 끝나는 경우
    matches = [r for r in registered_names if r.endswith(name) and r != name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) >= 2:
        raise AmbiguousNameError(name, matches)
    return name                            # 4) 매칭 없음 → 그대로(미등록)


def resolve_names(input_names, registered_names=None):
    """참석자 리스트 전체를 보정. 모호한 이름이 하나라도 있으면 즉시 중단."""
    if registered_names is None:
        registered_names = list(PLAYER_ABILITIES.keys())
    return [resolve_name(n, registered_names) for n in input_names]


# 합산점수 → 종합 등급 (표시용). 만점 = 항목수 × 4 (A)
_MAX_SCORE = len(ABILITY_KEYS) * 4   # 6항목 × 4 = 24


def get_grade(name):
    """합산점수를 비율로 환산해 A/B/C/D 종합 등급(표시용)으로 반환."""
    if is_mercenary(name):
        return MERCENARY_GRADE
    ratio = get_score(name) / _MAX_SCORE
    if ratio >= 0.80:
        return "A"
    if ratio >= 0.60:
        return "B"
    if ratio >= 0.40:
        return "C"
    return "D"


def get_score(name):
    """세부 능력치 등급을 합산한 점수 (grades.player_score)."""
    return player_score(name)


def team_score(team):
    return sum(get_score(p) for p in team)


# ─────────────────────────────────────────
# 팀 크기 / 벤치 결정
# ─────────────────────────────────────────

def determine_format(n):
    """
    최대 6:6 운영 원칙
    - 12명 이하 짝수 → n//2 : n//2, 벤치 0
    - 홀수           → (n-1)//2 : (n-1)//2, 벤치 1
    - 13명           → 6:6, 벤치 1
    - 14명           → 6:6, 벤치 2
    - 15명           → 6:6, 벤치 3
    """
    if n < 8:
        raise ValueError("최소 8명 이상이어야 합니다.")
    if n <= 12:
        team_size = n // 2
        bench = n % 2
    else:
        team_size = 6
        bench = n - 12
    return team_size, bench


# ─────────────────────────────────────────
# 벤치 배정 (용병 우선, 전원 최소 1회)
# ─────────────────────────────────────────

def make_bench_schedule(players, num_sets, bench_size, mercenary_set):
    if bench_size == 0:
        return [[] for _ in range(num_sets)]

    bench_candidates = list(players)
    merc_list   = [p for p in bench_candidates if p in mercenary_set]
    member_list = [p for p in bench_candidates if p not in mercenary_set]

    total_slots  = num_sets * bench_size
    n_candidates = len(bench_candidates)

    # 목표 휴식 횟수: 전원 1회 보장 후 남은 슬롯을 용병→회원 순 배분
    target = {p: 1 for p in bench_candidates}
    extra  = total_slots - n_candidates
    for p in merc_list + member_list:
        if extra <= 0:
            break
        target[p] += 1
        extra -= 1

    bench_slots  = []
    rested_once  = set()
    extra_used   = {p: 0 for p in bench_candidates}
    last_benched = set()

    for s in range(num_sets):
        chosen = []

        # Phase 1: 아직 못 쉰 사람 먼저
        p1 = [p for p in bench_candidates if p not in rested_once]
        non_con = [p for p in p1 if p not in last_benched]
        con     = [p for p in p1 if p in last_benched]
        random.shuffle(non_con); random.shuffle(con)
        for p in non_con + con:
            if len(chosen) >= bench_size:
                break
            chosen.append(p)

        # Phase 2: 추가 휴식 대상 (용병 우선)
        if len(chosen) < bench_size:
            p2_merc   = [p for p in merc_list   if p not in chosen and extra_used[p] < target[p] - 1]
            p2_member = [p for p in member_list if p not in chosen and extra_used[p] < target[p] - 1]
            def p2sort(lst):
                nc = [p for p in lst if p not in last_benched]
                c  = [p for p in lst if p in last_benched]
                random.shuffle(nc); random.shuffle(c)
                return nc + c
            for p in p2sort(p2_merc) + p2sort(p2_member):
                if len(chosen) >= bench_size:
                    break
                chosen.append(p)

        # fallback
        if len(chosen) < bench_size:
            fb = [p for p in bench_candidates if p not in chosen]
            random.shuffle(fb)
            chosen += fb[:bench_size - len(chosen)]

        for p in chosen:
            if p not in rested_once:
                rested_once.add(p)
            else:
                extra_used[p] += 1

        last_benched = set(chosen)
        bench_slots.append(chosen)

    return bench_slots


# ─────────────────────────────────────────
# 팀 배정 점수
# ─────────────────────────────────────────

def get_positions(player):
    """선수의 (1순위, 2순위) 포지션 반환. 미등록이면 (None, None)"""
    return PLAYER_POSITIONS.get(player, (None, None))


def position_coverage_penalty(team):
    """
    팀 내 포지션 커버리지 패널티 (낮을수록 좋음).
    이상적 포지션(ST/CM/RB/LB/CB) 중 팀에서 커버 못하는 포지션 수를 반환.
    1순위로 먼저 채우고, 빈 자리는 2순위로 채움.
    """
    covered = set()
    for p in team:
        pos1, pos2 = get_positions(p)
        if pos1:
            covered.add(pos1)
    # 2순위로 추가 커버
    for p in team:
        pos1, pos2 = get_positions(p)
        if pos2:
            covered.add(pos2)
    missing = len([pos for pos in IDEAL_POSITIONS if pos not in covered])
    return missing


def position_balance_penalty(team_a, team_b):
    """
    두 팀 간 포지션 커버 불균형 패널티.
    각 팀의 커버 포지션 수 차이 + 각 팀 내 미커버 포지션 수 합산.
    """
    miss_a = position_coverage_penalty(team_a)
    miss_b = position_coverage_penalty(team_b)
    return miss_a + miss_b


def balance_penalty(team_a, team_b):
    """두 팀의 점수 합 차이 — 0에 가까울수록 밸런스 좋음"""
    return abs(team_score(team_a) - team_score(team_b))


def pair_sum(team, tm):
    return sum(tm[p1][p2] for p1, p2 in itertools.combinations(team, 2))


def pair_max(team, tm):
    pairs = list(itertools.combinations(team, 2))
    return max((tm[p1][p2] for p1, p2 in pairs), default=0)


def pair_zero_bonus(team_a, team_b, tm):
    """0회 쌍이 많을수록 좋음 (음수 반환)"""
    count = sum(1 for p1, p2 in itertools.combinations(team_a, 2) if tm[p1][p2] == 0)
    count += sum(1 for p1, p2 in itertools.combinations(team_b, 2) if tm[p1][p2] == 0)
    return -count


def tm_add(tm, team):
    for p1, p2 in itertools.combinations(team, 2):
        tm[p1][p2] += 1
        tm[p2][p1] += 1


def assignment_score(team_a, team_b, prev_a, prev_b, target_overlap, running_tm):
    """낮을수록 좋음
    1. 밸런스 (팀 점수 차)           ← 최우선
    2. 등급 분산 (각 팀 내 등급 다양성)
    3. 0회 쌍 묶기
    4. 최대 겹침 억제
    5. 전체 쌍 합 최소
    6. 연속 중복도
    """
    bal = balance_penalty(team_a, team_b)

    # 등급 다양성: 팀 내 등급 점수 표준편차 (낮을수록 한쪽에 쏠림)
    def grade_spread(team):
        scores = [get_score(p) for p in team]
        mean = sum(scores) / len(scores)
        var  = sum((s - mean) ** 2 for s in scores) / len(scores)
        return var
    # 다양성이 높을수록(분산 클수록) 좋으므로 음수 패널티
    diversity_bonus = -(grade_spread(team_a) + grade_spread(team_b))

    zero_b  = pair_zero_bonus(team_a, team_b, running_tm)
    max_p   = pair_max(team_a, running_tm) + pair_max(team_b, running_tm)
    sum_p   = pair_sum(team_a, running_tm) + pair_sum(team_b, running_tm)

    overlap_a = len(set(team_a) & prev_a)
    overlap_b = len(set(team_b) & prev_b)
    consec    = abs(overlap_a - target_overlap) + abs(overlap_b - target_overlap)

    pos_pen = position_balance_penalty(team_a, team_b)

    return (bal * 500
            + pos_pen * 80
            + diversity_bonus * 50
            + zero_b * 200
            + max_p * 150
            + sum_p * 10
            + consec)


# ─────────────────────────────────────────
# 스케줄 생성
# ─────────────────────────────────────────

def generate_schedule(players, num_sets, team_size, bench_schedule, attempts=5000):
    mercenary_set = {p for p in players if is_mercenary(p)}
    all_players   = players

    best_schedule = None
    best_score    = float('inf')

    target_overlap = max(2, int(team_size * 0.5))

    for attempt in range(attempts):
        schedule   = []
        prev_a     = set()
        prev_b     = set()
        running_tm = defaultdict(lambda: defaultdict(int))

        for s in range(num_sets):
            bench   = bench_schedule[s]
            active  = [p for p in all_players if p not in bench]

            best_team      = None
            best_game_score = float('inf')

            for _ in range(150):
                shuffled = active.copy()
                random.shuffle(shuffled)
                team_a = shuffled[:team_size]
                team_b = shuffled[team_size:]

                if s > 0:
                    sc = assignment_score(team_a, team_b, prev_a, prev_b,
                                          target_overlap, running_tm)
                    if sc < best_game_score:
                        best_game_score = sc
                        best_team = (list(team_a), list(team_b), list(bench))
                else:
                    best_team = (list(team_a), list(team_b), list(bench))
                    break

            if best_team:
                schedule.append(best_team)
                prev_a = set(best_team[0])
                prev_b = set(best_team[1])
                tm_add(running_tm, best_team[0])
                tm_add(running_tm, best_team[1])

        if len(schedule) != num_sets:
            continue

        # 전체 스케줄 점수: 밸런스 총합 + 겹침 분산
        total_bal = sum(balance_penalty(g[0], g[1]) for g in schedule)
        all_counts = [running_tm[p1][p2]
                      for p1 in players for p2 in players if p1 < p2]
        if all_counts:
            mean = sum(all_counts) / len(all_counts)
            variance = sum((c - mean) ** 2 for c in all_counts) / len(all_counts)
        else:
            variance = 0
        score = total_bal * 100 + variance * 20

        if score < best_score:
            best_score    = score
            best_schedule = schedule

        if attempt == 0 or (attempt + 1) % 1000 == 0:
            print(f"  시도 {attempt+1}/{attempts}: 최고점수 {best_score:.1f}")

    return best_schedule


# ─────────────────────────────────────────
# 출력
# ─────────────────────────────────────────

GRADE_EMOJI = {"A": "🟠", "B": "🟢", "C": "⚪", "D": "⬛"}


def fmt_player(name):
    tag = "(용)" if is_mercenary(name) else ""
    return f"{name}{tag}"


OPPOSITE = {"RB": "LB", "LB": "RB"}
# CM 대체 포지션 (5인제에서 CM 선호 선수가 밀렸을 때)
CM_FALLBACK = "CB"


def alt(pos):
    if pos == "CM":
        return [CM_FALLBACK]
    if pos in OPPOSITE:
        return [OPPOSITE[pos]]
    return []


def assign_positions(field, ideal_positions, pos_counts=None):
    """
    필드 선수(GK 제외)에게 포지션 배정.

    라운드 순서:
      R1. 1순위   — 충돌 시 해당 포지션 횟수 적은 사람 우선, 동률이면 등급 낮은 사람
      R2. 2순위   — 같은 방식
      R3. 1순위 대체 (CM→CB, LB↔RB)
      R4. 2순위 대체 (CM→CB, LB↔RB)
      R5. 남은 ideal 자리 — 적게 한 포지션 우선 (CB 순환 핵심)
      R6. 미등록 선수 → 남은 자리
    """
    from collections import Counter as _Counter
    assigned = {}
    taken = _Counter()                      # 포지션별 채워진 수 (CM 2개 등 중복 지원)
    cap = _Counter(ideal_positions)         # 포지션별 정원 (ideal 에 CM 2개면 cap[CM]=2)
    if pos_counts is None:
        pos_counts = {}

    def cnt(p, pos):
        return pos_counts.get(p, {}).get(pos, 0)

    def _has_room(pos):
        return pos and taken[pos] < cap[pos]

    def try_assign(p, pos):
        if _has_room(pos):
            assigned[p] = pos
            taken[pos] += 1
            return True
        return False

    def resolve_group(group, get_pos_fn):
        losers = []
        if not group:
            return losers
        pos_groups = {}
        for p in group:
            pos = get_pos_fn(p)
            if pos:
                pos_groups.setdefault(pos, []).append(p)
            else:
                losers.append(p)
        for pos, g in pos_groups.items():
            # 해당 포지션 횟수 적은 순, 동률이면 등급 낮은 순
            sorted_g = sorted(g, key=lambda p: (cnt(p, pos), get_score(p)))
            if not try_assign(sorted_g[0], pos):
                losers.extend(sorted_g)
            else:
                losers.extend(sorted_g[1:])
        return losers

    unregistered = [p for p in field if get_positions(p) == (None, None)]
    registered   = [p for p in field if p not in unregistered]

    # R1: 1순위
    r2 = resolve_group(registered, lambda p: get_positions(p)[0])
    # R2: 2순위
    r3 = resolve_group(r2, lambda p: get_positions(p)[1])

    # R3: 1순위 대체
    alt_r3 = {}
    r4 = []
    for p in r3:
        pos1, _ = get_positions(p)
        found = False
        for a in alt(pos1):
            if _has_room(a):
                alt_r3.setdefault(a, []).append(p)
                found = True
                break
        if not found:
            r4.append(p)
    for a_pos, cands in alt_r3.items():
        sc = sorted(cands, key=lambda p: (cnt(p, a_pos), get_score(p)))
        if try_assign(sc[0], a_pos):
            r4.extend(sc[1:])
        else:
            r4.extend(sc)

    # R4: 2순위 대체
    alt_r4 = {}
    r5 = []
    for p in r4:
        _, pos2 = get_positions(p)
        found = False
        for a in alt(pos2):
            if _has_room(a):
                alt_r4.setdefault(a, []).append(p)
                found = True
                break
        if not found:
            r5.append(p)
    for a_pos, cands in alt_r4.items():
        sc = sorted(cands, key=lambda p: (cnt(p, a_pos), get_score(p)))
        if try_assign(sc[0], a_pos):
            r5.extend(sc[1:])
        else:
            r5.extend(sc)

    # R5: 등록 선수 — 적게 한 포지션 우선 (CB 자동 순환)
    for p in r5:
        available = [pos for pos in dict.fromkeys(ideal_positions) if _has_room(pos)]
        if available:
            best = min(available, key=lambda pos: cnt(p, pos))
            try_assign(p, best)
        else:
            assigned[p] = "?"

    # R6: 미등록 선수 — 남은 자리
    for p in unregistered:
        available = [pos for pos in dict.fromkeys(ideal_positions) if _has_room(pos)]
        if available:
            best = min(available, key=lambda pos: cnt(p, pos))
            try_assign(p, best)
        else:
            assigned[p] = "?"

    return assigned


def assign_all_cases(team, ideal_positions):
    """
    모든 GK 케이스를 순서대로 계산하면서 포지션 횟수를 누적.
    앞 케이스에서 많이 한 포지션은 뒤 케이스에서 피하도록 → 골고루 순환.
    매 경기 독립적으로 1~6번 케이스 생성.
    """
    from collections import defaultdict
    pos_counts = {p: defaultdict(int) for p in team}
    results = []

    for gk in team:
        pos_counts[gk]['GK'] = pos_counts[gk].get('GK', 0) + 1
        field = [p for p in team if p != gk]
        assigned = assign_positions(field, ideal_positions, pos_counts)
        for p, pos in assigned.items():
            pos_counts[p][pos] = pos_counts[p].get(pos, 0) + 1
        results.append((gk, assigned))

    return results


def assign_with_gk(team, gk, ideal_positions):
    field = [p for p in team if p != gk]
    return assign_positions(field, ideal_positions)


def print_gk_cases(team, team_label, ideal_positions):
    """GK별 포지션을 누적 순환 방식으로 출력 — 케이스마다 포지션이 골고루 돌아감"""
    seen = []
    for p in ideal_positions:
        if p not in seen:
            seen.append(p)
    field_pos = seen

    cases = assign_all_cases(team, ideal_positions)

    print(f"\n  ━━ {team_label} ━━")
    for idx, (gk, pos_map) in enumerate(cases, 1):
        print(f"\n  {idx}.")
        print(f"  {'GK':<4} {gk}")
        for pos in field_pos:
            player = next((p for p, v in pos_map.items() if v == pos), "-")
            print(f"  {pos:<4} {player}")
    print()


def print_game_schedule(team_a, team_b, rot_a, rot_b, ideal, num_games, label="메인팀"):
    """경기별로 벤치 + GK 포지션을 한 줄씩 컴팩트하게 출력"""
    seen = []
    for p in ideal:
        if p not in seen:
            seen.append(p)
    field_pos = seen  # ex) [ST, RB, LB, CB] or [ST, CM, RB, LB, CB]

    gk_order_a = list(team_a)
    gk_order_b = list(team_b)

    W = 140
    print(f"\n{'=' * W}")
    print(f"  {label}   (블랙 {sum(get_score(p) for p in team_a)}점  vs  화이트 {sum(get_score(p) for p in team_b)}점)")
    print(f"  {'─' * (W-2)}")
    print(f"  블랙 👕   {', '.join(f'{p}({get_score(p)})' for p in team_a)}")
    print(f"  화이트 👕  {', '.join(f'{p}({get_score(p)})' for p in team_b)}")
    print(f"{'=' * W}")

    for g in range(num_games):
        active_a, bench_a, sa = rot_a[g]
        active_b, bench_b, sb = rot_b[g]
        bench_a_str = ', '.join(bench_a) if bench_a else '-'
        bench_b_str = ', '.join(bench_b) if bench_b else '-'

        print(f"\n  {'─' * (W-2)}")
        print(f"  {g+1}경기   블랙 👕 벤치: {bench_a_str} ({sa}점)   │   화이트 👕 벤치: {bench_b_str} ({sb}점)")
        print(f"  {'─' * (W-2)}")

        # 베이스 팀 순서를 유지하되, 교차경기 임대 선수(상대 베이스 소속)도 빠뜨리지 않음
        set_a, set_b = set(active_a), set(active_b)
        active_gk_order_a = ([p for p in gk_order_a if p in set_a]
                             + [p for p in active_a if p not in set(gk_order_a)])
        active_gk_order_b = ([p for p in gk_order_b if p in set_b]
                             + [p for p in active_b if p not in set(gk_order_b)])

        cases_a = assign_all_cases(active_gk_order_a, ideal)
        cases_b = assign_all_cases(active_gk_order_b, ideal)

        # 헤더
        L = 68
        print(f"  {'블랙 👕':<{L}}화이트 👕")

        n_cases = max(len(cases_a), len(cases_b))
        for idx in range(n_cases):
            # 블랙 한 줄
            if idx < len(cases_a):
                gk_a, pm_a = cases_a[idx]
                parts_a = [f"GK {gk_a}"] + [f"{pos} {next((p for p,v in pm_a.items() if v==pos), '-')}" for pos in field_pos]
                line_a = f"{idx+1}. " + " /  ".join(parts_a)
            else:
                line_a = ""

            # 화이트 한 줄
            if idx < len(cases_b):
                gk_b, pm_b = cases_b[idx]
                parts_b = [f"GK {gk_b}"] + [f"{pos} {next((p for p,v in pm_b.items() if v==pos), '-')}" for pos in field_pos]
                line_b = f"{idx+1}. " + " /  ".join(parts_b)
            else:
                line_b = ""

            print(f"  {line_a:<{L}}{line_b}")

    print(f"\n{'=' * W}")


def print_schedule(schedule, players):
    W = 110
    print("=" * W)
    print("⚽ 팀 배정 결과")
    print("=" * W)

    prev_a = []
    prev_b = []

    for i, game in enumerate(schedule, 1):
        team_a, team_b, bench = game

        # 팀 크기에 따라 포지션 구성 선택
        ideal = IDEAL_POSITIONS_6 if len(team_a) >= 6 else IDEAL_POSITIONS_5

        sa = team_score(team_a)
        sb = team_score(team_b)

        # 유니폼 교환 인원
        if i == 1:
            swap_str = "없음 (첫 경기)"
        else:
            swappers = [p for p in prev_a if p in team_b] + [p for p in prev_b if p in team_a]
            swap_str = ', '.join(fmt_player(p) for p in swappers) if swappers else "없음"

        print(f"\n{'='*60}")
        print(f"  매치 {i}   블랙 👕 {sa}점  vs  화이트 👕 {sb}점")
        print(f"  🔄 유니폼 교환: {swap_str}")
        if bench:
            print(f"  🪑 벤치: {', '.join(fmt_player(p) for p in bench)}")

        # ── GK 경우의 수 ─────────────────────────────────────────
        print_gk_cases(team_a, f"매치 {i} 블랙팀 👕", ideal)
        print_gk_cases(team_b, f"매치 {i} 화이트팀 👕", ideal)

        prev_a = list(team_a)
        prev_b = list(team_b)

    print("\n" + "=" * W)


def print_statistics(schedule, players):
    running_tm = defaultdict(lambda: defaultdict(int))
    for game in schedule:
        tm_add(running_tm, game[0])
        tm_add(running_tm, game[1])

    all_counts = [running_tm[p1][p2] for p1 in players for p2 in players if p1 < p2]
    if not all_counts:
        return

    mn = min(all_counts)
    mx = max(all_counts)
    mean = sum(all_counts) / len(all_counts)

    print("\n📊 같은 팀 횟수 분포")
    print(f"  최소: {mn}회 | 최대: {mx}회 | 평균: {mean:.1f}회 | 범위: {mx - mn}회")

    from collections import Counter
    dist = Counter(all_counts)
    for k in sorted(dist):
        bar = "█" * (dist[k] // 2 + 1)
        print(f"  {k}회: {bar} ({dist[k]}쌍)")

    print()
    W = 130
    print("=" * W)
    print("📋 선수별 등급 및 세트별 배정")
    print("-" * W)
    header = f"{'선수':<12} {'등급':<6} {'선호포지션':<10} {'세트별':<25} {'같은팀총횟수'}"
    print(header)
    print("-" * W)

    rest_count = defaultdict(int)
    assign     = {p: [] for p in players}
    for game in schedule:
        team_a, team_b, bench = game
        for p in team_a:
            assign[p].append('A')
        for p in team_b:
            assign[p].append('B')
        for p in bench:
            assign[p].append('-')
            rest_count[p] += 1

    for p in players:
        grade  = get_grade(p)
        emoji  = GRADE_EMOJI.get(grade, "")
        tag    = "(용)" if is_mercenary(p) else ""
        seq    = ''.join(assign[p])
        total  = sum(running_tm[p][o] for o in players if o != p)
        rest   = f" (벤치 {rest_count[p]}회)" if rest_count[p] else ""
        pos1, pos2 = get_positions(p)
        pos_str = f"{pos1}/{pos2}" if pos1 else "-"
        print(f"{p+tag:<12} {emoji+grade:<7} {pos_str:<10} {seq:<25} {total}회{rest}")

    print("=" * W)


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def make_fixed_team_rotation(team, num_games, bench_per_team):
    """
    고정 팀 내에서 경기별 벤치 로테이션 생성.

    전략:
      1. 전체 벤치 슬롯(num_games × bench_per_team)을 n명에게 균등 배분
      2. quota=2인 선수는 간격이 최대(앞/뒤로 분산)가 되도록 미리 경기 번호 배정
      3. 나머지 슬롯은 연속 방지 + 점수 균형으로 그리디 배정
    """
    import math
    from itertools import combinations, permutations

    n = len(team)
    active_size = n - bench_per_team
    team_total  = sum(get_score(p) for p in team)
    avg_active  = team_total * active_size / n

    total_slots = num_games * bench_per_team
    base_quota  = total_slots // n
    extra_cnt   = total_slots % n

    # extra 1회: 점수 낮은 선수 우선
    sorted_by_score = sorted(range(n), key=lambda i: get_score(team[i]))
    bench_quota = [base_quota] * n
    for i in sorted_by_score[:extra_cnt]:
        bench_quota[i] += 1

    # ── 미리 계획: quota>=2인 선수의 벤치 경기를 최대 간격으로 배정 ──
    # bench_plan[g] = set of player_idx
    bench_plan = [set() for _ in range(num_games)]
    occupied   = [0] * num_games  # 경기별 현재 배정된 벤치 인원

    double_players = [i for i in range(n) if bench_quota[i] >= 2]
    # quota=2이면 num_games // 2 간격으로 배정 → 앞 절반, 뒤 절반
    for i in double_players:
        q = bench_quota[i]
        gap = num_games // q
        slots = []
        # 점수 낮을수록 앞에 배정 (더 자주 벤치)
        rank = sorted_by_score.index(i)
        offset = rank % gap
        for k in range(q):
            g = (offset + k * gap) % num_games
            slots.append(g)
        # 간격 검증: 연속이면 한 칸 밀기
        slots.sort()
        adjusted = [slots[0]]
        for s in slots[1:]:
            prev = adjusted[-1]
            if s - prev <= 1:
                s = prev + 2
                if s >= num_games:
                    s = max(0, adjusted[0] - 2)
            adjusted.append(s)
        for g in adjusted:
            g = min(g, num_games - 1)
            if occupied[g] < bench_per_team:
                bench_plan[g].add(i)
                occupied[g] += 1

    # ── 그리디로 나머지 채우기 ────────────────────────────────────
    bench_count     = [0] * n
    last_bench_game = [-99] * n

    # 미리 계획된 선수 반영
    for g in range(num_games):
        for i in bench_plan[g]:
            bench_count[i] += 1
            last_bench_game[i] = g

    rotation = []
    # 재배정: 이번엔 실제로 경기마다 벤치 결정
    bench_count     = [0] * n
    last_bench_game = [-99] * n

    for g in range(num_games):
        remaining = num_games - g

        # pre-plan에서 이 경기 배정된 선수 (must로 처리)
        pre = list(bench_plan[g])

        eligible = [i for i in range(n)
                    if bench_count[i] < bench_quota[i] and i not in pre]

        # must: 남은 경기에서 쿼터 못 채울 선수
        must_extra = [i for i in eligible
                      if (bench_quota[i] - bench_count[i]) >= remaining]

        must = pre + [i for i in must_extra if i not in pre]
        free_slots = bench_per_team - len(must)
        free_pool  = [i for i in eligible if i not in must]

        # 정렬: 연속 후순위, 오래 쉬지 않은 사람 우선
        free_pool.sort(key=lambda i: (
            1 if last_bench_game[i] == g - 1 else 0,
            -(g - last_bench_game[i]),
        ))

        best_combo  = None
        best_g_err  = float('inf')
        search_pool = free_pool[:min(len(free_pool), 7)]

        for extra in combinations(search_pool, max(0, free_slots)):
            combo = must + list(extra)
            if len(combo) != bench_per_team:
                continue
            combo_set = set(combo)
            consec = sum(1 for i in combo if last_bench_game[i] == g - 1)
            active_score = sum(get_score(team[i]) for i in range(n) if i not in combo_set)
            err = abs(active_score - avg_active) + consec * 60
            if err < best_g_err:
                best_g_err, best_combo = err, combo

        if best_combo is None:
            best_combo = (must + free_pool)[:bench_per_team]

        for i in best_combo:
            bench_count[i] += 1
            last_bench_game[i] = g

        bench_players  = [team[i] for i in best_combo]
        active_players = [p for p in team if p not in set(bench_players)]
        active_score   = sum(get_score(p) for p in active_players)
        rotation.append((active_players, bench_players, active_score))

    return rotation


def build_external_rotation(players):
    """
    10명 미만 외부 매칭 모드.
    우리팀 6명 출전, 나머지 벤치 로테이션. 8경기.
    반환: {
        'mode': 'external',
        'n': 인원수, 'ideal': IDEAL_POSITIONS_6,
        'players': players,
        'rotation': [(active6, bench, active_score), ...]  # 8경기
    }
    """
    import math
    n = len(players)
    NUM_GAMES = 8

    if n < 5:
        raise NotEnoughPlayersError(
            f"외부 매칭은 최소 5명부터 가능해요. (현재 {n}명)"
        )

    # 5명이면 5:5(CM 없음), 6명 이상이면 6:6
    if n == 5:
        TEAM_SIZE = 5
        ideal = IDEAL_POSITIONS_5
    else:
        TEAM_SIZE = 6
        ideal = IDEAL_POSITIONS_6

    if n <= TEAM_SIZE:
        # 출전 인원과 같거나 적으면 벤치 없이 전원 출전
        rot = [(list(players), [], sum(get_score(p) for p in players))] * NUM_GAMES
        return {'mode': 'external', 'n': n, 'ideal': ideal, 'players': players, 'rotation': rot}

    bench_per_game = n - TEAM_SIZE
    total_slots = NUM_GAMES * bench_per_game
    base_bench = total_slots // n
    extra = total_slots % n

    # 점수 낮은 순으로 extra 배분
    sorted_by_score = sorted(players, key=lambda p: get_score(p))
    bench_quota = {p: base_bench for p in players}
    for p in sorted_by_score[:extra]:
        bench_quota[p] += 1

    # ── 벤치 스케줄 미리 계획: 각 선수별 벤치 경기를 최대 간격으로 배분 ──
    # quota=2이면 4경기 간격(1,5 or 2,6 등), quota=1이면 아무 경기
    from itertools import combinations as _comb

    avg_active = sum(get_score(p) for p in players) * TEAM_SIZE / n

    # 선수별 벤치 경기 번호를 미리 결정 (전체 탐색)
    # bench_per_game명씩 8경기 → 조합 최적화
    # 간격 최대화 + 점수 균형을 동시에 고려

    # Step1: 각 선수의 벤치 슬롯 간격 최대화 스케줄 생성
    def gen_spaced_slots(quota, n_games, offset=0):
        """quota회를 n_games 경기에 최대 간격으로 배치"""
        if quota == 0:
            return []
        gap = n_games // quota
        return [(offset + i * gap) % n_games for i in range(quota)]

    # 선수별 초기 벤치 경기 후보
    sorted_players = sorted(players, key=lambda p: get_score(p))
    player_bench_games = {}
    for idx, p in enumerate(sorted_players):
        q = bench_quota[p]
        # 점수 낮은 순으로 앞 경기부터 배치 (offset으로 분산)
        offset = idx % (NUM_GAMES // max(q, 1))
        player_bench_games[p] = gen_spaced_slots(q, NUM_GAMES, offset)

    # Step2: 경기별 bench_per_game 명 정확히 맞도록 조정 + 점수 균형
    # 각 경기별 후보 선수 집계
    game_bench_map = {g: [] for g in range(NUM_GAMES)}
    for p, games_list in player_bench_games.items():
        for g in games_list:
            game_bench_map[g].append(p)

    # 경기별 인원이 bench_per_game보다 많으면 점수 균형 기준으로 줄이고,
    # 부족하면 쿼터 남은 선수 중 간격 가장 큰 선수 추가
    final_bench = {g: [] for g in range(NUM_GAMES)}
    bench_used = {p: 0 for p in players}
    last_bench = {p: -99 for p in players}

    for g in range(NUM_GAMES):
        candidates = [p for p in game_bench_map[g] if bench_used[p] < bench_quota[p]]

        # bench_per_game 보다 많으면 점수 균형 기준 최적 조합 선택
        if len(candidates) > bench_per_game:
            best, best_err = None, float('inf')
            for combo in _comb(candidates, bench_per_game):
                active_score = sum(get_score(p) for p in players if p not in set(combo))
                err = abs(active_score - avg_active)
                if err < best_err:
                    best_err, best = err, list(combo)
            candidates = best

        # bench_per_game 보다 적으면 보충
        while len(candidates) < bench_per_game:
            remaining_quota = [
                p for p in players
                if bench_used[p] < bench_quota[p] and p not in candidates
            ]
            if not remaining_quota:
                break
            # 마지막 벤치로부터 간격 가장 큰 선수 선택 (연속 방지 + 간격 최대)
            remaining_quota.sort(key=lambda p: (
                1 if last_bench[p] == g - 1 else 0,
                -(g - last_bench[p])
            ))
            # 점수 균형도 고려해서 최적 1명 추가
            best_add, best_err = None, float('inf')
            cur_set = set(candidates)
            for p in remaining_quota[:6]:
                active_score = sum(get_score(q) for q in players if q not in cur_set and q != p)
                err = abs(active_score - avg_active) + (60 if last_bench[p] == g - 1 else 0)
                if err < best_err:
                    best_err, best_add = err, p
            if best_add:
                candidates.append(best_add)
            else:
                break

        for p in candidates:
            bench_used[p] += 1
            last_bench[p] = g
        final_bench[g] = candidates

    rotation = []
    for g in range(NUM_GAMES):
        bench = final_bench[g]
        active = [p for p in players if p not in set(bench)]
        rotation.append((active, bench, sum(get_score(p) for p in active)))

    return {'mode': 'external', 'n': n, 'ideal': ideal, 'players': players, 'rotation': rotation}


def build_small_self(players, tries=3000):
    """
    8명 이하 소수 자체전: 등급 기반 균등 두 팀 분배. 포메이션 없이 이름만.
    반환: {'mode': 'small_self', 'team_a': [...], 'team_b': [...]}
    """
    n = len(players)
    half = n // 2
    best_a, best_b, best_diff = None, None, float('inf')
    for _ in range(tries):
        s = players[:]
        random.shuffle(s)
        a, b = s[:half], s[half:]
        diff = abs(sum(get_score(p) for p in a) - sum(get_score(p) for p in b))
        if diff < best_diff:
            best_diff, best_a, best_b = diff, a[:], b[:]
    return {'mode': 'small_self', 'team_a': best_a, 'team_b': best_b}


def make_odd_rotation(base_a, base_b, team_size, num_games=8):
    """홀수 인원 교차 로테이션 (매 경기 team_size:team_size 유지).

    큰팀 A(블랙) = ⌈n/2⌉, 작은팀 B(화이트) = ⌊n/2⌋  (A = B+1)
      · 기본경기: A가 a_base=|A|-T, B가 b_base=|B|-T 명 벤치
      · 교차경기: A가 (a_base-1) 벤치 + 1명을 화이트로 임대,
                  B가 (b_base+1) 벤치  → 양 팀 모두 필드 T명
    교차경기 수 c는 양 팀의 1인당 휴식 횟수가 최대한 같아지도록 자동 선택한다.

    반환: (rot_a, rot_b)  각각 [(active, bench, active_score), ...] num_games개
    """
    A, B = list(base_a), list(base_b)
    nA, nB = len(A), len(B)
    a_base = nA - team_size
    b_base = nB - team_size
    # A = B+1 이므로 a_base = b_base+1 이 보장됨 (방어적으로 음수만 차단)
    a_base = max(a_base, 0)
    b_base = max(b_base, 0)

    # ── 교차경기 수 c 결정: A/B 1인당 휴식 균형 ──
    #   A_per = (num_games*a_base - c)/nA,  B_per = (num_games*b_base + c)/nB
    best_c, best_gap = 0, float('inf')
    c_max = num_games if a_base >= 1 else 0   # 교차경기는 A가 1명 이상 벤치 가능해야 함
    for c in range(0, c_max + 1):
        a_per = (num_games * a_base - c) / nA
        b_per = (num_games * b_base + c) / nB
        gap = abs(a_per - b_per)
        if gap < best_gap:
            best_gap, best_c = gap, c
    c = best_c

    # ── 경기 타입 시퀀스: 교차경기를 전체에 고르게 분산 ──
    is_cross = [False] * num_games
    if c > 0:
        step = num_games / c
        for k in range(c):
            idx = int(round(k * step + step / 2)) % num_games
            while is_cross[idx]:
                idx = (idx + 1) % num_games
            is_cross[idx] = True

    a_benches = [a_base - 1 if t else a_base for t in is_cross]
    b_benches = [b_base + 1 if t else b_base for t in is_cross]

    def pick_team_bench(team, bench_counts):
        """팀 내 경기별 벤치 선정: quota 균등, 연속 회피, 낮은 점수 우선 벤치."""
        total = sum(bench_counts)
        m = len(team)
        base_q, extra = divmod(total, m)
        order = sorted(team, key=get_score)      # 점수 낮을수록 벤치 많이
        quota = {p: base_q for p in team}
        for p in order[:extra]:
            quota[p] += 1
        used = {p: 0 for p in team}
        last = {p: -99 for p in team}
        picks = []
        for g, k in enumerate(bench_counts):
            remaining = len(bench_counts) - g
            must = [p for p in team
                    if 0 < quota[p] - used[p] >= remaining]
            pool = [p for p in team if used[p] < quota[p] and p not in must]
            pool.sort(key=lambda p: (1 if last[p] == g - 1 else 0,
                                     -(g - last[p]), get_score(p)))
            bench = list(must)
            for p in pool:
                if len(bench) >= k:
                    break
                bench.append(p)
            bench = bench[:k]
            for p in bench:
                used[p] += 1
                last[p] = g
            picks.append(bench)
        return picks

    a_bench_games = pick_team_bench(A, a_benches)
    b_bench_games = pick_team_bench(B, b_benches)

    rot_a, rot_b = [], []
    for g in range(num_games):
        bench_a = a_bench_games[g]
        bench_b = b_bench_games[g]
        a_field = [p for p in A if p not in set(bench_a)]
        b_field = [p for p in B if p not in set(bench_b)]
        if is_cross[g] and len(a_field) > team_size:
            # 블랙 필드에서 1명을 화이트로 임대 — 양 팀 점수차가 최소가 되게 선택
            target = (sum(get_score(p) for p in a_field)
                      - sum(get_score(p) for p in b_field)) / 2
            mover = min(a_field, key=lambda p: abs(get_score(p) - target))
            a_field = [p for p in a_field if p != mover]
            b_field = b_field + [mover]
        rot_a.append((a_field, bench_a, sum(get_score(p) for p in a_field)))
        rot_b.append((b_field, bench_b, sum(get_score(p) for p in b_field)))
    return rot_a, rot_b


def build_rotation(players, fixed_same=None, fixed_diff=None, seven_v_seven=False):
    """
    참여자 리스트를 받아 메인팀/스페어팀 로테이션 데이터를 반환.
    seven_v_seven: 14명 자체전일 때 7:7(벤치 0)로 진행
    반환: {
        'n': 인원수, 'team_size': 팀크기, 'ideal': 포지션목록,
        'main': {'base_a', 'base_b', 'rot_a', 'rot_b'},
        'spare': {'base_a', 'base_b', 'rot_a', 'rot_b'} or None
    }
    """
    n = len(players)
    # 14명 이상 + 7:7 플래그: 경기당 팀 7명 출전(초과 인원은 벤치 로테이션), CM 2명 포지션
    use_7v7 = seven_v_seven and n >= 14
    if use_7v7:
        team_size = 7
        ideal = IDEAL_POSITIONS_7
    else:
        team_size, _ = determine_format(n)
        ideal = IDEAL_POSITIONS_6 if team_size >= 6 else IDEAL_POSITIONS_5
    NUM_GAMES = 8

    def find_best(size, tries=3000, fixed_same=None, fixed_diff=None):
        """
        fixed_same: 같은 팀으로 묶을 선수 리스트 (a팀 또는 b팀 어디든 같이)
        fixed_diff: 다른 팀으로 분리할 (p1, p2) 튜플 리스트
        """
        fixed_same = fixed_same or []
        fixed_diff = fixed_diff or []
        best_a, best_b, best_diff = None, None, float('inf')
        for _ in range(tries):
            s = players[:]
            random.shuffle(s)
            a, b = s[:size], s[size:]
            set_a, set_b = set(a), set(b)

            # FIXED_SAME_TEAM: 모두 같은 팀에 있어야 함
            if fixed_same:
                in_a = [p for p in fixed_same if p in set_a]
                in_b = [p for p in fixed_same if p in set_b]
                if in_a and in_b:  # 양 팀에 분산 → 버림
                    continue

            # FIXED_DIFF_TEAM: 각 쌍이 다른 팀에 있어야 함
            skip = False
            for p1, p2 in fixed_diff:
                if (p1 in set_a and p2 in set_a) or (p1 in set_b and p2 in set_b):
                    skip = True
                    break
            if skip:
                continue

            if n % 2 == 1:
                avg = sum(get_score(p) for p in a) * team_size / size
                diff = abs(avg - sum(get_score(p) for p in b))
            else:
                diff = abs(sum(get_score(p) for p in a) - sum(get_score(p) for p in b))
            if diff < best_diff:
                best_diff, best_a, best_b = diff, a[:], b[:]
        return best_a, best_b

    fs = fixed_same or []
    fd = fixed_diff or []

    if n % 2 == 1:
        # 홀수: 큰팀/작은팀으로 나누고 교차 로테이션으로 매 경기 team_size:team_size 유지
        a_size = (n + 1) // 2
        base_a, base_b = find_best(a_size, fixed_same=fs, fixed_diff=fd)
        rot_a, rot_b = make_odd_rotation(base_a, base_b, team_size, NUM_GAMES)
        spare = None
    else:
        size = n // 2                       # 홀수면 큰 팀이 1명 더 (벤치 로테이션으로 흡수)
        a_size = n - size                   # 블랙 = 나머지(홀수일 때 +1)
        bench_a = a_size - team_size        # 블랙 팀 벤치 수
        bench_b = size - team_size          # 화이트 팀 벤치 수
        base_a, base_b = find_best(a_size, fixed_same=fs, fixed_diff=fd)
        rot_a = make_fixed_team_rotation(base_a, NUM_GAMES, bench_a)
        rot_b = make_fixed_team_rotation(base_b, NUM_GAMES, bench_b)
        sp_a, sp_b = find_best(a_size, fixed_same=fs, fixed_diff=fd)
        sp_rot_a = make_fixed_team_rotation(sp_a, NUM_GAMES, bench_a)
        sp_rot_b = make_fixed_team_rotation(sp_b, NUM_GAMES, bench_b)
        spare = {'base_a': sp_a, 'base_b': sp_b, 'rot_a': sp_rot_a, 'rot_b': sp_rot_b}

    return {
        'n': n, 'team_size': team_size, 'ideal': ideal, 'num_games': NUM_GAMES,
        'main':  {'base_a': base_a, 'base_b': base_b, 'rot_a': rot_a, 'rot_b': rot_b},
        'spare': spare,
    }


def main():
    players = list(MEMBERS)
    n       = len(players)
    mercenary_set = {p for p in players if is_mercenary(p)}

    print("⚽ 풋살 팀 배정기 ⚽")
    print("=" * 110)

    print(f"참여 인원 ({n}명):")
    for p in players:
        grade = get_grade(p)
        emoji = GRADE_EMOJI.get(grade, "")
        tag   = " (용병)" if is_mercenary(p) else ""
        print(f"  {p}{tag} → {emoji} {grade}  ({get_score(p)}점)")
    print()

    try:
        team_size, bench_size = determine_format(n)
    except ValueError as e:
        print(f"❌ {e}")
        return

    ideal = IDEAL_POSITIONS_6 if team_size >= 6 else IDEAL_POSITIONS_5
    W = 110
    NUM_GAMES = 8

    if n % 2 == 1:
        # ── 홀수: 블랙 ⌈n/2⌉ / 화이트 ⌊n/2⌋, 교차 로테이션으로 매 경기 team_size:team_size ──
        team_a_size = (n + 1) // 2
        team_b_size = n // 2
        print(f"게임 형식: {team_size}:{team_size}  블랙 {team_a_size}명 / 화이트 {team_b_size}명  경기 수: {NUM_GAMES}경기")
        print(f"※ 홀수 인원: 매 경기 {team_size}:{team_size} 유지 — 기본경기(블랙 더 벤치)와 교차경기(블랙 1명 임시 화이트)를 섞어 전원 골고루 휴식")
        print()

        print("🔍 메인팀 탐색 중...")
        best_team_a, best_team_b = None, None
        best_team_score = float('inf')
        for _ in range(3000):
            shuffled = players.copy()
            random.shuffle(shuffled)
            ta = shuffled[:team_a_size]
            tb = shuffled[team_a_size:]
            # 블랙(큰팀) 출전 team_size명 추정 점수 ≈ 화이트(작은팀) 출전 team_size명 점수
            avg_active_a = sum(get_score(p) for p in ta) * team_size / team_a_size
            avg_active_b = sum(get_score(p) for p in tb) * team_size / team_b_size
            diff = abs(avg_active_a - avg_active_b)
            if diff < best_team_score:
                best_team_score = diff
                best_team_a, best_team_b = ta[:], tb[:]

        base_a = best_team_a  # 블랙 (큰팀)
        base_b = best_team_b  # 화이트 (작은팀)

        rot_a_full, rot_b_full = make_odd_rotation(base_a, base_b, team_size, NUM_GAMES)

        print()
        print_game_schedule(base_a, base_b, rot_a_full, rot_b_full, ideal, NUM_GAMES, "⚽ 메인팀")

    else:
        # ── 짝수(10/12/14명): 기존 로직 ─────────────────────────────
        team_total_size = n // 2
        bench_per_team  = team_total_size - team_size

        print(f"게임 형식: {team_size}:{team_size}  팀당 인원: {team_total_size}명 (경기 {team_size}명 + 벤치 {bench_per_team}명)  경기 수: {NUM_GAMES}경기")
        print()

        print("🔍 메인팀 탐색 중...")
        best_team_a, best_team_b = None, None
        best_team_score = float('inf')
        for _ in range(3000):
            shuffled = players.copy()
            random.shuffle(shuffled)
            team_a = shuffled[:team_total_size]
            team_b = shuffled[team_total_size:]
            diff = abs(sum(get_score(p) for p in team_a) - sum(get_score(p) for p in team_b))
            if diff < best_team_score:
                best_team_score = diff
                best_team_a, best_team_b = team_a[:], team_b[:]

        base_a = best_team_a
        base_b = best_team_b

        rot_a = make_fixed_team_rotation(base_a, NUM_GAMES, bench_per_team)
        rot_b = make_fixed_team_rotation(base_b, NUM_GAMES, bench_per_team)

        print()
        print_game_schedule(base_a, base_b, rot_a, rot_b, ideal, NUM_GAMES, "⚽ 메인팀")

    # ── 스페어팀 (짝수일 때만) ────────────────────────────────────
    if n % 2 == 0:
        print("\n🔍 스페어팀 탐색 중...")
        best_sp_a, best_sp_b = None, None
        best_sp_score = float('inf')

        for _ in range(3000):
            shuffled = players.copy()
            random.shuffle(shuffled)
            sp_a = shuffled[:team_total_size]
            sp_b = shuffled[team_total_size:]
            diff = abs(sum(get_score(p) for p in sp_a) - sum(get_score(p) for p in sp_b))
            if diff < best_sp_score:
                best_sp_score = diff
                best_sp_a = sp_a[:]
                best_sp_b = sp_b[:]

        sp_rot_a = make_fixed_team_rotation(best_sp_a, NUM_GAMES, bench_per_team)
        sp_rot_b = make_fixed_team_rotation(best_sp_b, NUM_GAMES, bench_per_team)

        print()
        print_game_schedule(best_sp_a, best_sp_b, sp_rot_a, sp_rot_b, ideal, NUM_GAMES,
                            "🔄 스페어팀 (메인팀 밸런스 무너졌을 때 사용)")


if __name__ == "__main__":
    main()
