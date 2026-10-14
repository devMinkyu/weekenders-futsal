#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
풋살 팀 배정 결과를 HTML로 출력 (탭 기반 UI)
python3 export_html.py  →  result.html 생성 후 브라우저로 자동 오픈
"""

import os, sys, json, webbrowser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from team_maker import (
    MEMBERS, determine_format, get_score, get_grade, get_positions,
    assign_all_cases, build_rotation, build_external_rotation, build_small_self,
)
try:
    from members import GAME_MODE, FIXED_SAME_TEAM, FIXED_DIFF_TEAM
except ImportError:
    GAME_MODE, FIXED_SAME_TEAM, FIXED_DIFF_TEAM = "auto", [], []

# ── 포지션 좌표 (SVG 300×460 기준) ───────────────────────────
POS_XY_5 = {"GK":(175,490),"LB":(65,360),"CB":(175,360),"RB":(285,360),"ST":(175,170)}
POS_XY_6 = {"GK":(175,490),"LB":(65,375),"CB":(175,375),"RB":(285,375),"CM":(175,255),"ST":(175,135)}

_svg_counter = [0]

def svg_court(pos_map, team="black", is_6v6=False, bench_players=None):
    _svg_counter[0] += 1
    gid = f"grass{_svg_counter[0]}"  # 각 SVG마다 고유 gradient id

    W, H = 350, 540
    pos_xy = POS_XY_6 if is_6v6 else POS_XY_5
    fill   = "#1e1e1e" if team == "black" else "#f5f5f5"
    text   = "#ffffff" if team == "black" else "#111111"
    stroke = "#555"    if team == "black" else "#bbb"

    svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#2d8a2d"/>
      <stop offset="50%" stop-color="#3aa33a"/>
      <stop offset="100%" stop-color="#2d8a2d"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="12" fill="url(#{gid})"/>
  <!-- 잔디 줄무늬 -->
  <g opacity="0.15">
    {''.join(f'<rect x="0" y="{i*34}" width="{W}" height="17" fill="#ffffff"/>' for i in range(H//34+1))}
  </g>
  <g stroke="rgba(255,255,255,0.9)" stroke-width="2.5" fill="none">
    <rect x="14" y="14" width="{W-28}" height="{H-28}" rx="5"/>
    <line x1="14" y1="{H//2}" x2="{W-14}" y2="{H//2}"/>
    <circle cx="{W//2}" cy="{H//2}" r="48"/>
    <circle cx="{W//2}" cy="{H//2}" r="4" fill="rgba(255,255,255,0.8)" stroke="none"/>
    <rect x="{W//2-40}" y="{H-14}" width="80" height="14"/>
    <path d="M{W//2-80},{H-14} A 80,80 0 0,1 {W//2+80},{H-14}"/>
    <rect x="{W//2-70}" y="{H-76}" width="140" height="62"/>
    <rect x="{W//2-40}" y="0" width="80" height="14"/>
    <path d="M{W//2-80},14 A 80,80 0 0,0 {W//2+80},14"/>
    <rect x="{W//2-70}" y="14" width="140" height="62"/>
  </g>'''

    for pos, name in pos_map.items():
        if not name or pos not in pos_xy:
            continue
        x, y = pos_xy[pos]
        svg += f'''
  <g transform="translate({x},{y})" class="player-node" data-player="{name}" style="cursor:pointer">
    <circle r="30" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
    <text y="-6" text-anchor="middle" fill="{text}" font-size="14" font-weight="700"
      font-family="-apple-system,AppleGothic,sans-serif">{name}</text>
    <text y="12" text-anchor="middle" fill="{text}" font-size="11" opacity="0.7"
      font-family="-apple-system,AppleGothic,sans-serif">{pos}</text>
  </g>'''

    # 벤치 선수 — 오른쪽 아래 코너에 원형으로 표시
    if bench_players:
        bx_start = W - 36
        by_start = H - 36
        for i, bp in enumerate(bench_players):
            bx = bx_start - i * 62
            svg += f'''
  <g transform="translate({bx},{by_start})">
    <circle r="28" fill="rgba(0,0,0,0.6)" stroke="rgba(255,255,255,0.7)" stroke-width="2" stroke-dasharray="5,3"/>
    <text y="-6" text-anchor="middle" fill="#fff" font-size="13" font-weight="700"
      font-family="-apple-system,AppleGothic,sans-serif">{bp}</text>
    <text y="11" text-anchor="middle" fill="rgba(255,255,255,0.75)" font-size="10"
      font-family="-apple-system,AppleGothic,sans-serif">벤치</text>
  </g>'''

    svg += '\n</svg>'
    return svg

# ── 데이터를 JSON으로 직렬화 ──────────────────────────────────
def build_section_data(team_a, team_b, rot_a, rot_b, ideal, num_games):
    seen = []
    for p in ideal:
        if p not in seen:
            seen.append(p)
    field_pos = seen
    is_6v6 = "CM" in field_pos
    gk_order_a = list(team_a)
    gk_order_b = list(team_b)

    # 경기 간 GK 슬롯 위치 유지 (벤치 교체 시 나간 선수 슬롯을 들어오는 선수가 이어받음)
    # prev_order_a/b: 직전 경기의 GK 순서 리스트
    prev_order_a = list(gk_order_a)
    prev_order_b = list(gk_order_b)

    games = []
    for g in range(num_games):
        active_a, bench_a, _ = rot_a[g]
        active_b, bench_b, _ = rot_b[g]

        active_set_a = set(active_a)
        active_set_b = set(active_b)

        # GK 순서 결정: 직전 경기 순서 기준으로 유지
        # 빠진 선수(벤치) 자리에 들어온 선수(복귀/임시투입)를 그 슬롯에 삽입
        def build_gk_order(prev_order, active_set, active):
            result = []
            incoming = [p for p in active if p not in set(prev_order)]  # 새로 들어온 선수
            inc_iter = iter(incoming)
            for p in prev_order:
                if p in active_set:
                    result.append(p)
                else:
                    # 이 슬롯에 나간 선수 대신 들어온 선수 배치
                    replacement = next(inc_iter, None)
                    if replacement:
                        result.append(replacement)
            # 혹시 못 들어간 선수 있으면 뒤에 추가
            for p in active:
                if p not in result:
                    result.append(p)
            return result

        active_gk_a = build_gk_order(prev_order_a, active_set_a, active_a)
        active_gk_b = build_gk_order(prev_order_b, active_set_b, active_b)

        # 다음 경기를 위해 현재 순서 저장
        prev_order_a = active_gk_a
        prev_order_b = active_gk_b

        cases_a = assign_all_cases(active_gk_a, ideal)
        cases_b = assign_all_cases(active_gk_b, ideal)

        cases_svg = []
        for idx in range(max(len(cases_a), len(cases_b))):
            svg_a, svg_b = "", ""
            if idx < len(cases_a):
                gk, pm = cases_a[idx]
                pm_full = {"GK": gk, **{pos: next((p for p,v in pm.items() if v==pos), '') for pos in field_pos}}
                svg_a = svg_court(pm_full, "black", is_6v6, bench_a if bench_a else None)
            if idx < len(cases_b):
                gk, pm = cases_b[idx]
                pm_full = {"GK": gk, **{pos: next((p for p,v in pm.items() if v==pos), '') for pos in field_pos}}
                svg_b = svg_court(pm_full, "white", is_6v6, bench_b if bench_b else None)
            cases_svg.append({"black": svg_a, "white": svg_b})

        # 선수별 케이스별 포지션 배열 (모달용)
        # {player: ['GK', 'LB', 'CB', ...]} — 케이스 순서대로
        def collect_player_pos_seq(cases, bench, team_label):
            result = {}
            for gk, pm in cases:
                result.setdefault(gk, []).append('GK')
                for player, pos in pm.items():
                    if player:
                        result.setdefault(player, []).append(pos)
            for p in bench:
                result[p] = ['벤치']
            return result, {p: team_label for p in result}

        player_pos_a, team_label_a = collect_player_pos_seq(cases_a, bench_a, '블랙')
        player_pos_b, team_label_b = collect_player_pos_seq(cases_b, bench_b, '화이트')

        # 임시 투입 선수 감지: 원래 team_a인데 이번 경기 team_b 포지션에 있으면 guest
        orig_a = set(team_a)
        orig_b = set(team_b)
        guest_map = {}  # {player: True} — 이 경기에서 임시 이동한 선수
        for p in player_pos_b:
            if p in orig_a:
                guest_map[p] = True
        for p in player_pos_a:
            if p in orig_b:
                guest_map[p] = True

        games.append({
            "bench_a": ', '.join(bench_a) if bench_a else '-',
            "bench_b": ', '.join(bench_b) if bench_b else '-',
            "cases": cases_svg,
            "player_pos": {**player_pos_a, **player_pos_b},
            "player_team": {**team_label_a, **team_label_b},
            "player_guest": guest_map,
        })

    # 벤치 요약: 선수별 경기별 출전/벤치 여부
    all_players = list(team_a) + list(team_b)
    bench_summary = []
    for p in all_players:
        row = []
        for g in games:
            benched = [x.strip() for x in (g['bench_a'] + ',' + g['bench_b']).split(',') if x.strip()]
            row.append('bench' if p in benched else 'play')
        bench_summary.append({
            'name': p,
            'row': row,
            'count': row.count('bench'),
        })

    return {
        "team_a": team_a,
        "team_b": team_b,
        "games": games,
        "bench_summary": bench_summary,
    }

# ── 외부 매칭 HTML 생성 ───────────────────────────────────────
def build_external_section(ext):
    """외부 매칭 모드용 섹션 데이터 구성"""
    players  = ext['players']
    rotation = ext['rotation']
    ideal    = ext['ideal']
    NUM_GAMES = len(rotation)

    seen = []
    for p in ideal:
        if p not in seen:
            seen.append(p)
    field_pos = seen
    is_6v6 = "CM" in field_pos

    prev_order = list(players)
    games = []
    for active, bench, _ in rotation:
        active_set = set(active)
        # 벤치 나간 자리에 들어온 선수 슬롯 이어받기
        result = []
        incoming = [p for p in active if p not in set(prev_order)]
        inc_iter = iter(incoming)
        for p in prev_order:
            if p in active_set:
                result.append(p)
            else:
                replacement = next(inc_iter, None)
                if replacement:
                    result.append(replacement)
        for p in active:
            if p not in result:
                result.append(p)
        prev_order = result
        cases = assign_all_cases(result, ideal)
        cases_svg = []
        player_pos = {}
        for gk, pm in cases:
            player_pos.setdefault(gk, []).append('GK')
            for player, pos in pm.items():
                if player:
                    player_pos.setdefault(player, []).append(pos)
        for p in bench:
            player_pos[p] = ['벤치']
        # 매칭은 단일팀이라 team/guest 없이 빈 값
        player_team  = {p: '' for p in player_pos}
        player_guest = {}
        for gk, pm in cases:
            pm_full = {"GK": gk, **{pos: next((p for p,v in pm.items() if v==pos), '') for pos in field_pos}}
            svg = svg_court(pm_full, "black", is_6v6, bench if bench else None)
            cases_svg.append({"svg": svg, "gk": gk})
        games.append({
            "bench": ', '.join(bench) if bench else '-',
            "active": active,
            "cases": cases_svg,
            "player_pos":   player_pos,
            "player_team":  player_team,
            "player_guest": player_guest,
        })

    # 벤치 요약
    bench_summary = []
    for p in players:
        row = ['bench' if p in g['bench'].split(', ') else 'play' for g in games]
        bench_summary.append({'name': p, 'row': row, 'count': row.count('bench')})

    return {
        "players": players,
        "games": games,
        "bench_summary": bench_summary,
    }


# ── HTML 생성 ─────────────────────────────────────────────────
def generate_html():
    players = list(MEMBERS)
    n = len(players)

    # 모드 결정
    # Enum 또는 문자열 모두 지원
    mode_val = GAME_MODE.value if hasattr(GAME_MODE, 'value') else str(GAME_MODE)
    IS_SMALL_SELF = False
    if mode_val == "match":
        IS_EXTERNAL = True
        mode_note = ""
    elif mode_val == "self":
        if n < 10:
            IS_EXTERNAL = False
            IS_SMALL_SELF = True
            mode_note = f"⚠️ 10명 미만 자체전 ({n}명) — 포메이션 없이 팀 구분만 제공"
            print(f"ℹ️  소수 자체전 ({n}명): 팀 이름만 표시")
        else:
            IS_EXTERNAL = False
            mode_note = ""
    else:  # auto
        IS_EXTERNAL = n < 10
        mode_note = ""

    print("🔍 팀 배정 중...")

    if IS_SMALL_SELF:
        small = build_small_self(players)
        team_a = small['team_a']
        team_b = small['team_b']
        sa = sum(get_score(p) for p in team_a)
        sb = sum(get_score(p) for p in team_b)
        team_size = len(team_a)
        NUM_GAMES = 0
        ideal = []
        all_data = []
        has_spare = False
        data_js = "const DATA = [];"
        ext_data_js = "const EXT = null;"
        small_js = f"const SMALL = {json.dumps({'team_a': team_a, 'team_b': team_b, 'score_a': sa, 'score_b': sb}, ensure_ascii=False)};"
    elif IS_EXTERNAL:
        ext = build_external_rotation(players)
        ext_section = build_external_section(ext)
        ideal     = ext['ideal']
        NUM_GAMES = len(ext['rotation'])
        team_size = 6
        all_data  = []
        ext_data_js = f"const EXT = {json.dumps(ext_section, ensure_ascii=False)};"
        has_spare = False
        data_js   = "const DATA = [];"
        small_js  = "const SMALL = null;"
    else:
        small_js = "const SMALL = null;"
        try:
            team_size, _ = determine_format(n)
        except ValueError as e:
            print(f"❌ {e}"); return

        result = build_rotation(players, fixed_same=FIXED_SAME_TEAM, fixed_diff=FIXED_DIFF_TEAM)
        ideal     = result['ideal']
        NUM_GAMES = result['num_games']
        team_size = result['team_size']
        base_a    = result['main']['base_a']
        base_b    = result['main']['base_b']
        rot_a     = result['main']['rot_a']
        rot_b     = result['main']['rot_b']

        main_data = build_section_data(base_a, base_b, rot_a, rot_b, ideal, NUM_GAMES)

        spare_data = None
        if result['spare']:
            sp = result['spare']
            spare_data = build_section_data(sp['base_a'], sp['base_b'], sp['rot_a'], sp['rot_b'], ideal, NUM_GAMES)

        all_data = [main_data] if spare_data is None else [main_data, spare_data]
        data_js  = f"const DATA = {json.dumps(all_data, ensure_ascii=False)};"
        ext_data_js = "const EXT = null;"
        has_spare = spare_data is not None

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>⚽ 풋살 팀 배정</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
        background: #eef1f5; color: #111; min-height: 100vh; }}

/* 헤더 */
.app-header {{ background: #1a1a2e; color: #fff; text-align: center; padding: 20px 16px 0; }}
.app-header h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
.app-header p  {{ font-size: .9rem; color: #aaa; margin-bottom: 16px; }}

/* 메인/스페어 탭 */
.section-tabs {{ display: flex; justify-content: center; gap: 0; }}
.section-tab  {{ padding: 10px 32px; font-size: 1rem; font-weight: 700; cursor: pointer;
                 border: none; background: transparent; color: rgba(255,255,255,.5);
                 border-bottom: 3px solid transparent; transition: all .2s; }}
.section-tab.active {{ color: #fff; border-bottom-color: #4fc3f7; }}

/* 멤버 */
.members-section {{ background: #fff; padding: 14px 16px; margin-bottom: 0; }}
.members-section h3 {{ font-size: .95rem; color: #666; margin-bottom: 8px; padding: 0 2px; }}
.members-grid {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.member-card {{ background: #f8f9fa; border-radius: 10px; padding: 7px 10px; text-align: center; min-width: 72px; }}
.member-name {{ font-size: 1.05rem; font-weight: 700; }}
.member-pos  {{ font-size: .8rem; color: #888; margin-top: 3px; }}

/* 팀 로스터 */
.roster-bar {{ background: #fff; padding: 24px 32px; border-bottom: 1px solid #eee; }}
.roster-row {{ display: block; padding: 8px 0; }}
.roster-label {{ font-size: 1rem; font-weight: 700; display: block; margin-bottom: 10px; }}
.chips-wrap {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.clickable {{ cursor: pointer; }}
.clickable:hover {{ opacity: 0.75; }}
.player-chip {{ background: #f0f0f0; border-radius: 14px; padding: 6px 14px;
                font-size: .95rem; font-weight: 600; white-space: nowrap;
                display: inline-flex; flex-direction: column; align-items: center; gap: 1px; }}
.chip-pos {{ font-size: .72rem; color: #888; font-weight: 500; }}

/* 경기 탭바 */
.game-tabbar {{ display: flex; overflow-x: auto; background: #fff;
                border-bottom: 1px solid #ddd; padding: 0 8px;
                -webkit-overflow-scrolling: touch; }}
.game-tabbar::-webkit-scrollbar {{ height: 0; }}
.game-tab {{ flex: none; padding: 12px 16px; font-size: .95rem; font-weight: 600;
             cursor: pointer; border: none; background: transparent; color: #888;
             border-bottom: 3px solid transparent; white-space: nowrap; transition: all .2s; }}
.game-tab.active {{ color: #1a1a2e; border-bottom-color: #1a1a2e; }}

/* 경기 뷰 */
.game-view {{ padding: 16px; }}
.bench-banner {{ background: #1a1a2e; color: #fff; border-radius: 10px;
                  padding: 12px 18px; margin-bottom: 16px; font-size: 1rem; }}
.bench-banner .bench-sep {{ color: rgba(255,255,255,.4); margin: 0 10px; }}
.bench-name {{ font-size: 1.05rem; font-weight: 700; }}

/* 블랙/화이트 팀 탭 */
.team-tabbar {{ display: flex; justify-content: center; gap: 0; margin: 14px 0 4px; }}
.team-tab {{ flex: 1; max-width: 180px; padding: 10px 0; font-size: 1rem; font-weight: 700;
             cursor: pointer; border: none; background: #f0f0f0; color: #888;
             border-bottom: 3px solid transparent; transition: all .2s; }}
.team-tab:first-child {{ border-radius: 10px 0 0 0; }}
.team-tab:last-child  {{ border-radius: 0 10px 0 0; }}
.team-tab.active {{ background: #fff; color: #1a1a2e; border-bottom-color: #1a1a2e; }}

/* GK 케이스 네비게이션 */
.case-nav {{ display: flex; align-items: center; justify-content: center;
             gap: 16px; margin-bottom: 16px; }}
.case-nav button {{ background: #1a1a2e; color: #fff; border: none; border-radius: 50%;
                    width: 44px; height: 44px; font-size: 1.4rem; cursor: pointer; }}
.case-nav button:disabled {{ background: #ccc; cursor: default; }}
.case-indicator {{ font-size: 1.1rem; font-weight: 700; color: #333;
                   min-width: 90px; text-align: center; }}
.courts-pair {{ display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }}
.court-wrap  {{ display: flex; flex-direction: column; align-items: center; gap: 5px; }}
.court-label {{ font-size: 1rem; font-weight: 700; }}

/* 벤치 요약 */
.bench-summary {{ background: #fff; padding: 14px 20px; border-top: 1px solid #eee; }}
.bench-teams {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.bench-team-col {{ display: flex; flex-direction: column; gap: 8px; }}
.bench-team-label {{ font-size: .9rem; font-weight: 700; color: #444; margin-bottom: 4px; padding-bottom: 6px; border-bottom: 2px solid #eee; }}
.bench-list {{ display: flex; flex-direction: column; gap: 7px; }}
.bench-item {{ display: flex; align-items: center; gap: 8px; font-size: .9rem; flex-wrap: wrap; }}
.bench-item .bname {{ font-weight: 700; min-width: 58px; }}
.bench-tag, .no-bench {{ border-radius: 20px; padding: 3px 10px; font-size: .82rem;
                          font-weight: 600; white-space: nowrap;
                          display: inline-block; min-width: 160px; text-align: center; }}
.bench-tag {{ background: #ffebee; color: #c62828; }}
.no-bench  {{ background: #e8f5e9; color: #2e7d32; }}

/* 소수 자체전 */
.small-self-view {{ padding: 16px; display: flex; flex-direction: column; gap: 16px; }}
.small-team-row {{ background: #fff; border-radius: 12px; padding: 16px 20px;
                   box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.small-team-label {{ font-size: 1rem; font-weight: 700; margin-bottom: 10px; }}
.small-score {{ font-size: .85rem; color: #888; font-weight: 400; margin-left: 6px; }}

/* 선수 모달 */
.modal-overlay {{ position: fixed; inset: 0; background: rgba(0,0,0,.5);
                  z-index: 1000; display: flex; align-items: center; justify-content: center;
                  padding: 16px; }}
.modal-overlay.hidden {{ display: none; }}
.modal-box {{ background: #fff; border-radius: 16px; width: 100%; max-width: 420px;
               max-height: 85vh; display: flex; flex-direction: column;
               box-shadow: 0 8px 32px rgba(0,0,0,.3); overflow: hidden; }}
.modal-header {{ background: #1a1a2e; color: #fff; padding: 16px 20px;
                  border-radius: 16px 16px 0 0; display: flex; justify-content: space-between;
                  align-items: center; flex-shrink: 0; }}
.modal-body {{ overflow-y: auto; flex: 1; }}
.modal-header h3 {{ font-size: 1.2rem; }}
.modal-header .pos-tag {{ font-size: .85rem; background: rgba(255,255,255,.2);
                           border-radius: 20px; padding: 3px 10px; }}
.modal-close {{ background: none; border: none; color: #fff; font-size: 1.4rem; cursor: pointer; padding: 0 4px; }}
.modal-body {{ padding: 16px 20px; }}
.modal-game-row {{ display: flex; align-items: center; gap: 12px; padding: 10px 0;
                    border-bottom: 1px solid #f0f0f0; }}
.modal-game-row:last-child {{ border-bottom: none; }}
.modal-game-num {{ font-size: .85rem; font-weight: 700; color: #888; min-width: 44px; }}
.modal-pos-badge {{ border-radius: 20px; padding: 5px 14px; font-size: .9rem; font-weight: 700;
                     min-width: 64px; text-align: center; }}
.modal-pos-badge.bench {{ background: #ffebee; color: #c62828; }}
.modal-pos-badge.gk    {{ background: #fff3e0; color: #e65100; }}
.modal-pos-badge.st    {{ background: #e3f2fd; color: #1565c0; }}
.modal-pos-badge.cm    {{ background: #f3e5f5; color: #6a1b9a; }}
.modal-pos-badge.rb {{ background: #e8f5e9; color: #2e7d32; }}
.modal-pos-badge.lb {{ background: #e3f2fd; color: #0d47a1; }}
.modal-pos-badge.cb    {{ background: #fafafa; color: #555; border: 1px solid #ddd; }}
.modal-pos-seq {{ display: flex; flex-direction: column; gap: 4px; align-items: flex-start; }}
.modal-arrow {{ color: #bbb; font-size: .85rem; }}
.modal-team-tag {{ font-size: .8rem; color: #aaa; white-space: nowrap; }}
.modal-no-bench {{ padding: 16px 0; }}
.pos-row {{ display: flex; align-items: center; flex-wrap: nowrap; gap: 4px; margin-bottom: 4px; }}
.modal-team-tag.guest {{ color: #e65100; font-weight: 700; }}

/* 스페어 스타일 */
.spare .game-tab.active  {{ color: #555; border-bottom-color: #888; }}
.spare .bench-banner     {{ background: #4a4a6a; }}

/* 섹션 패널 */
.section-panel {{ display: none; }}
.section-panel.active {{ display: block; }}
</style>
</head>
<body>

<div class="app-header">
  <h1>⚽ 풋살 팀 배정</h1>
  <p>{n}명 참여 · {'외부 매칭 6:6' if IS_EXTERNAL else f'{team_size}:{team_size}'} · {NUM_GAMES}경기</p>
  {'<p style="color:#ffcc00;font-size:.85rem;margin-top:4px">' + mode_note + '</p>' if mode_note else ''}
  {'<div class="section-tabs"><button class="section-tab active" data-action="section" data-si="0">⚽ 메인팀</button>' + ('<button class="section-tab" data-action="section" data-si="1">🔄 스페어팀</button>' if has_spare else '') + '</div>' if not IS_EXTERNAL else ''}
</div>

<!-- 선수 모달 -->
<div id="player-modal" class="modal-overlay hidden">
  <div class="modal-box">
    <div class="modal-header">
      <h3 id="modal-name"></h3>
      <span id="modal-pos-tag" class="pos-tag"></span>
      <button class="modal-close" id="modal-close-btn">✕</button>
    </div>
    <div class="modal-body" id="modal-body"></div>
  </div>
</div>

{'<div id="section-0" class="section-panel active"></div>' if not IS_EXTERNAL and not IS_SMALL_SELF else ''}
{'<div id="small-view"></div>' if IS_SMALL_SELF else ''}
{'<div id="section-1" class="section-panel spare"></div>' if has_spare else ''}
{'<div id="ext-view"></div>' if IS_EXTERNAL else ''}

<script>
{data_js}
{ext_data_js}
{small_js}
const posMap = {json.dumps({p: (lambda pos: f"{pos[0]}/{pos[1]}" if pos[0] else "")(get_positions(p)) for p in players}, ensure_ascii=False)};

// 섹션별 상태: game(경기), gkCase(GK 케이스), team(0=블랙,1=화이트)
const state = [
  {{ game: 0, gkCase: 0, team: 0 }},
  {{ game: 0, gkCase: 0, team: 0 }},
];

// ── 이벤트 위임 ───────────────────────────────────────────────
document.addEventListener('click', function(e) {{
  // 선수 이름 클릭 → 모달
  const playerEl = e.target.closest('[data-player]');
  if (playerEl) {{
    const si = playerEl.dataset.si;
    if (si === 'small') {{
      openSmallModal(playerEl.dataset.player);
      return;
    }}
    // SVG 코트 내 선수 클릭이면 해당 경기/케이스 컨텍스트 전달
    const courtWrap = e.target.closest('[data-game]');
    if (courtWrap) {{
      const csi = courtWrap.dataset.si;
      const game = parseInt(courtWrap.dataset.game);
      const caseIdx = parseInt(courtWrap.dataset.case);
      openPlayerModal(playerEl.dataset.player, csi, game, caseIdx);
    }} else {{
      openPlayerModal(playerEl.dataset.player, si);
    }}
    openModal();
    return;
  }}

  const t = e.target.closest('[data-action]');
  if (!t) return;
  const action = t.dataset.action;
  // 외부 매칭 액션은 별도 리스너에서 처리
  if (action === 'ext-game' || action === 'ext-gk') return;
  const si = parseInt(t.dataset.si);
  if (action === 'section') {{ switchSection(si); return; }}
  const gi = parseInt(t.dataset.gi);
  if (action === 'game')    {{ switchGame(si, gi); return; }}
  if (action === 'team')    {{ switchTeam(si, gi); return; }}
  const delta = parseInt(t.dataset.delta);
  if (action === 'gk')      {{ shiftGK(si, delta); return; }}
}});

function switchSection(idx) {{
  document.querySelectorAll('.section-tab').forEach(function(t,i){{ t.classList.toggle('active', i===idx); }});
  document.querySelectorAll('.section-panel').forEach(function(p,i){{ p.classList.toggle('active', i===idx); }});
  renderSection(idx);
}}

function switchGame(si, gi) {{
  state[si].game   = gi;
  state[si].gkCase = 0;
  renderSection(si);
}}

function switchTeam(si, ti) {{
  state[si].team = ti;
  renderSection(si);
}}

function shiftGK(si, delta) {{
  const cases = DATA[si].games[state[si].game].cases;
  state[si].gkCase = Math.max(0, Math.min(cases.length - 1, state[si].gkCase + delta));
  renderSection(si);
}}

function renderSection(si) {{
  const sec = DATA[si];
  const st  = state[si];
  const panel = document.getElementById('section-' + si);
  const spareClass = si === 1 ? 'spare' : '';

  // 로스터
  function chipHtml(p) {{
    const pos = posMap[p] || '';
    return '<span class="player-chip clickable" data-player="' + p + '" data-si="' + si + '">'
      + p + (pos ? '<span class="chip-pos">' + pos + '</span>' : '') + '</span>';
  }}

  let html = '<div class="roster-bar ' + spareClass + '">'
    + '<div class="roster-row"><span class="roster-label">블랙 👕</span><div class="chips-wrap">'
    + sec.team_a.map(chipHtml).join('')
    + '</div></div>'
    + '<div class="roster-row"><span class="roster-label">화이트 👕</span><div class="chips-wrap">'
    + sec.team_b.map(chipHtml).join('')
    + '</div></div></div>';

  // 벤치 없으면 경기 탭 숨김 (모든 경기 동일)
  const hasBench = sec.games.some(function(g){{ return g.bench_a !== '-' || g.bench_b !== '-'; }});

  if (hasBench) {{
    html += '<div class="game-tabbar ' + spareClass + '">';
    sec.games.forEach(function(_, gi) {{
      const act = gi === st.game ? 'active' : '';
      html += '<button class="game-tab ' + act + '" data-action="game" data-si="' + si + '" data-gi="' + gi + '">' + (gi+1) + '경기</button>';
    }});
    html += '</div>';
  }}

  // 경기 뷰
  const game  = sec.games[st.game];
  const cases = game.cases;
  const ci    = Math.min(st.gkCase, cases.length - 1);
  const c     = cases[ci];

  // 블랙/화이트 팀 탭
  const teamLabels = ['🖤 블랙팀', '🤍 화이트팀'];
  let teamTabHtml = '<div class="team-tabbar">';
  teamLabels.forEach(function(label, ti) {{
    const act = ti === st.team ? 'active' : '';
    teamTabHtml += '<button class="team-tab ' + act + '" data-action="team" data-si="' + si + '" data-gi="' + ti + '">' + label + '</button>';
  }});
  teamTabHtml += '</div>';

  // GK 네비게이션
  const gkNav = '<div class="case-nav">'
    + '<button data-action="gk" data-si="' + si + '" data-delta="-1"' + (ci===0 ? ' disabled' : '') + '>‹</button>'
    + '<span class="case-indicator">⚽ ' + (ci+1) + '번 GK 포지션 <span style="font-size:.85rem;color:#888;font-weight:400">/ 총 ' + cases.length + '회전</span></span>'
    + '<button data-action="gk" data-si="' + si + '" data-delta="1"' + (ci===cases.length-1 ? ' disabled' : '') + '>›</button>'
    + '</div>';

  // 선택된 팀 코트
  const courtSvg = st.team === 0 ? c.black : c.white;
  const courtLabel = st.team === 0 ? '블랙 👕' : '화이트 👕';

  const benchBanner = hasBench
    ? '<div class="bench-banner">🖤 벤치: <span class="bench-name">' + game.bench_a + '</span><span class="bench-sep">│</span>🤍 벤치: <span class="bench-name">' + game.bench_b + '</span></div>'
    : '';

  html += '<div class="game-view">'
    + benchBanner
    + teamTabHtml
    + gkNav
    + '<div class="courts-pair">'
    + '<div class="court-wrap" data-si="' + si + '" data-game="' + st.game + '" data-case="' + ci + '">' + courtSvg + '</div>'
    + '</div>'
    + '</div>';

  // 벤치 요약 (팀별)
  const hasBenchData = sec.bench_summary && sec.bench_summary.some(function(r){{ return r.count > 0; }});
  if (hasBenchData) {{
    const setA = new Set(sec.team_a);
    const blackList = sec.bench_summary.filter(function(r){{ return setA.has(r.name); }});
    const whiteList = sec.bench_summary.filter(function(r){{ return !setA.has(r.name); }});

    function renderBenchList(list) {{
      return list.map(function(r) {{
        const benchGames = r.row.map(function(s, i){{ return s === 'bench' ? (i+1) + '경기' : null; }}).filter(Boolean);
        const tag = benchGames.length > 0
          ? '<span class="bench-tag">벤치 ' + r.count + '회 (' + benchGames.join(', ') + ')</span>'
          : '<span class="no-bench">✓ 전경기 출전</span>';
        return '<div class="bench-item"><span class="bname clickable" data-player="' + r.name + '" data-si="' + si + '">' + r.name + '</span>' + tag + '</div>';
      }}).join('');
    }}

    html += '<div class="bench-summary">'
      + '<div class="bench-teams">'
      + '<div class="bench-team-col"><div class="bench-team-label">🖤 블랙팀</div><div class="bench-list">' + renderBenchList(blackList) + '</div></div>'
      + '<div class="bench-team-col"><div class="bench-team-label">🤍 화이트팀</div><div class="bench-list">' + renderBenchList(whiteList) + '</div></div>'
      + '</div></div>';
  }}

  panel.innerHTML = html;
}}

// 소수 자체전 렌더
function renderSmall() {{
  const panel = document.getElementById('small-view');
  if (!panel || !SMALL) return;

  function playerChip(p) {{
    const pos = posMap[p] || '';
    return '<span class="player-chip clickable" data-player="' + p + '" data-si="small">'
      + p + (pos ? '<span class="chip-pos">' + pos + '</span>' : '') + '</span>';
  }}

  let html = '<div class="small-self-view">'
    + '<div class="small-team-row">'
    + '<div class="small-team-label">블랙 👕 <span class="small-score">' + SMALL.score_a + '점</span></div>'
    + '<div class="chips-wrap">' + SMALL.team_a.map(playerChip).join('') + '</div>'
    + '</div>'
    + '<div class="small-team-row">'
    + '<div class="small-team-label">화이트 👕 <span class="small-score">' + SMALL.score_b + '점</span></div>'
    + '<div class="chips-wrap">' + SMALL.team_b.map(playerChip).join('') + '</div>'
    + '</div>'
    + '</div>';

  panel.innerHTML = html;
}}

// ── 소수 자체전용 모달 (포지션만) ─────────────────────────────
function openSmallModal(name) {{
  const prefPos = posMap[name] || '';
  const posSeq = prefPos ? prefPos.split('/') : [];
  const posHtml = posSeq.length
    ? posSeq.map(function(pos) {{
        const cls = posColors[pos] || 'cb';
        return '<span class="modal-pos-badge ' + cls + '">' + pos + '</span>';
      }}).join('<span class="modal-arrow">→</span>')
    : '<span style="color:#aaa">포지션 미등록</span>';

  document.getElementById('modal-name').textContent = name;
  document.getElementById('modal-pos-tag').textContent = prefPos ? '선호: ' + prefPos : '';
  document.getElementById('modal-body').innerHTML =
    '<div class="modal-no-bench"><div class="modal-pos-seq">' + posHtml + '</div></div>';
  openModal();
}}

// 초기 렌더 — extState 선언 후 아래에서 실행

function renderExternal() {{
  const panel = document.getElementById('ext-view');
  if (!panel) return;

  // 참여 인원 (클릭 가능)
  let html = '<div class="roster-bar">'
    + '<div class="roster-row"><span class="roster-label">참여 인원</span><div class="chips-wrap">'
    + EXT.players.map(function(p) {{
        const pos = typeof posMap !== 'undefined' && posMap[p] ? posMap[p] : '';
        return '<span class="player-chip clickable" data-player="' + p + '" data-si="ext">'
          + p + (pos ? '<span class="chip-pos">' + pos + '</span>' : '') + '</span>';
      }}).join('')
    + '</div></div></div>';

  // 경기 탭바
  html += '<div class="game-tabbar">';
  EXT.games.forEach(function(_, gi) {{
    const act = gi === extState.game ? 'active' : '';
    html += '<button class="game-tab ' + act + '" data-action="ext-game" data-gi="' + gi + '">' + (gi+1) + '경기</button>';
  }});
  html += '</div>';

  const game = EXT.games[extState.game];
  const ci   = Math.min(extState.gkCase, game.cases.length - 1);
  const c    = game.cases[ci];

  // 벤치 배너
  const benchBanner = game.bench !== '-'
    ? '<div class="bench-banner">🪑 벤치: <span class="bench-name">' + game.bench + '</span></div>'
    : '';

  // GK 네비
  const gkNav = '<div class="case-nav">'
    + '<button data-action="ext-gk" data-delta="-1"' + (ci===0?' disabled':'') + '>‹</button>'
    + '<span class="case-indicator">⚽ ' + (ci+1) + '번 GK 포지션 <span style="font-size:.85rem;color:#888;font-weight:400">/ 총 ' + game.cases.length + '회전</span></span>'
    + '<button data-action="ext-gk" data-delta="1"' + (ci===game.cases.length-1?' disabled':'') + '>›</button>'
    + '</div>';

  html += '<div class="game-view">' + benchBanner + gkNav
    + '<div class="courts-pair"><div class="court-wrap" data-si="ext" data-game="' + extState.game + '" data-case="' + ci + '">' + c.svg + '</div></div></div>';

  // 벤치 요약
  const hasBench = EXT.bench_summary.some(function(r){{ return r.count > 0; }});
  if (hasBench) {{
    html += '<div class="bench-summary"><h4>🪑 벤치 현황</h4><div class="bench-list">';
    EXT.bench_summary.forEach(function(r) {{
      const benchGames = r.row.map(function(s,i){{ return s==='bench'?(i+1)+'경기':null; }}).filter(Boolean);
      const tag = benchGames.length > 0
        ? '<span class="bench-tag">벤치 ' + r.count + '회 (' + benchGames.join(', ') + ')</span>'
        : '<span class="no-bench">✓ 전경기 출전</span>';
      html += '<div class="bench-item"><span class="bname clickable" data-player="' + r.name + '" data-si="ext">' + r.name + '</span>' + tag + '</div>';
    }});
    html += '</div></div>';
  }}

  panel.innerHTML = html;
}}

const extState = {{ game: 0, gkCase: 0 }};

// ── 선수 모달 ─────────────────────────────────────────────────
const posColors = {{ GK:'gk', ST:'st', CM:'cm', RB:'rb', LB:'lb', CB:'cb', '벤치':'bench', '-':'none' }};

function openPlayerModal(name, si, focusGame, focusCase) {{
  const sec = (si === 'ext') ? EXT : (DATA[si] || null);
  if (!sec) return;

  // 포지션 선호 정보
  const prefPos = typeof posMap !== 'undefined' && posMap[name] ? posMap[name] : '';
  // 코트에서 클릭 시 해당 경기/케이스만 보여줄지 여부
  const fromCourt = (focusGame !== undefined && focusCase !== undefined);

  function makePosHtml(posSeq, highlightIdx) {{
    const isBench = posSeq.length === 1 && posSeq[0] === '벤치';
    if (isBench) return '<span class="modal-pos-badge bench">벤치</span>';
    const parts = posSeq.map(function(pos, i) {{
      const cls = posColors[pos] || 'cb';
      const hl = (highlightIdx !== undefined && i === highlightIdx)
        ? ' style="box-shadow:0 0 0 3px #f5c400;background:#fff3b0!important;color:#333!important"' : '';
      return '<span class="modal-pos-badge ' + cls + '"' + hl + '>' + pos + '</span>';
    }});
    const row1 = parts.slice(0, 3).join('<span class="modal-arrow">→</span>');
    const row2 = parts.slice(3).join('<span class="modal-arrow">→</span>');
    return row2
      ? '<div class="pos-row">' + row1 + '</div><div class="pos-row">' + row2 + '</div>'
      : '<div class="pos-row">' + row1 + '</div>';
  }}

  // 벤치가 있는지 확인
  const hasBench = sec.bench_summary
    ? sec.bench_summary.some(function(r){{ return r.count > 0; }})
    : (sec.games && sec.games.some(function(g){{ return g.bench !== '-' && g.bench; }}));

  let bodyHtml = '';

  if (fromCourt) {{
    // 코트에서 클릭 → 해당 경기 + 해당 케이스 하이라이트
    const g = sec.games[focusGame];
    const posSeq = g && g.player_pos ? (g.player_pos[name] || ['벤치']) : ['벤치'];
    const teamTag = g && g.player_team ? (g.player_team[name] || '') : '';
    const isGuest = g && g.player_guest ? !!g.player_guest[name] : false;
    const teamLine = teamTag
      ? '<br><span style="font-size:.8rem;' + (isGuest ? 'color:#e65100;font-weight:700' : 'color:#aaa') + '">(' + teamTag + ')</span>'
      : '';
    bodyHtml = '<div class="modal-game-row">'
      + '<span class="modal-game-num" style="line-height:1.8">' + (focusGame+1) + '경기' + teamLine + '</span>'
      + '<div class="modal-pos-seq">' + makePosHtml(posSeq, focusCase) + '</div>'
      + '</div>';
  }} else if (!hasBench) {{
    // 벤치 없음 → 경기 구분 없이 포지션 순서 한 번만
    const g0 = sec.games[0];
    const posSeq = g0 && g0.player_pos ? (g0.player_pos[name] || ['?']) : ['?'];
    bodyHtml = '<div class="modal-no-bench">'
      + '<div class="modal-pos-seq">' + makePosHtml(posSeq) + '</div>'
      + '</div>';
  }} else {{
    // 벤치 있음 → 경기별 표시 (연속 동일 포지션 그룹핑)
    const rows = sec.games.map(function(g, gi) {{
      const posSeq  = g.player_pos   ? (g.player_pos[name]   || ['벤치']) : ['벤치'];
      const teamTag = g.player_team  ? (g.player_team[name]  || '') : '';
      const isGuest = g.player_guest ? !!g.player_guest[name] : false;
      return {{ game: gi + 1, posSeq, posKey: posSeq.join(','), teamTag, isGuest }};
    }});

    const groups = [];
    rows.forEach(function(r) {{
      const last = groups[groups.length - 1];
      if (last && last.posKey === r.posKey && last.teamTag === r.teamTag && last.isGuest === r.isGuest) {{
        last.games.push(r.game);
      }} else {{
        groups.push({{ games: [r.game], posSeq: r.posSeq, posKey: r.posKey, teamTag: r.teamTag, isGuest: r.isGuest }});
      }}
    }});

    bodyHtml = groups.map(function(grp) {{
      const teamLine = grp.teamTag
        ? '<br><span style="font-size:.8rem;font-weight:400;' + (grp.isGuest ? 'color:#e65100;font-weight:700' : 'color:#aaa') + '">(' + grp.teamTag + ')</span>'
        : '';
      const gameLabel = grp.games.map(function(g, idx) {{
        return g + '경기' + (idx === grp.games.length - 1 ? teamLine : '');
      }}).join('<br>');
      return '<div class="modal-game-row">'
        + '<span class="modal-game-num" style="line-height:1.8">' + gameLabel + '</span>'
        + '<div class="modal-pos-seq">' + makePosHtml(grp.posSeq) + '</div>'
        + '</div>';
    }}).join('');
  }}

  document.getElementById('modal-name').textContent = name;
  document.getElementById('modal-pos-tag').textContent = prefPos ? '선호: ' + prefPos : '';
  document.getElementById('modal-body').innerHTML = bodyHtml;
  document.getElementById('player-modal').classList.remove('hidden');
}}

function closeModal() {{
  document.getElementById('player-modal').classList.add('hidden');
  document.body.style.overflow = '';
}}
function openModal() {{
  document.getElementById('player-modal').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}}

document.getElementById('modal-close-btn').addEventListener('click', closeModal);
document.getElementById('player-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeModal();
}});

// 초기 렌더
if (typeof SMALL !== 'undefined' && SMALL) {{
  renderSmall();
}} else if (typeof EXT !== 'undefined' && EXT) {{
  renderExternal();
}} else {{
  renderSection(0);
  renderSection(1);
}}

document.addEventListener('click', function(e) {{
  const t = e.target.closest('[data-action]');
  if (!t) return;
  const action = t.dataset.action;
  if (action === 'ext-game') {{
    extState.game = parseInt(t.dataset.gi);
    extState.gkCase = 0;
    renderExternal();
  }} else if (action === 'ext-gk') {{
    const cases = EXT.games[extState.game].cases;
    extState.gkCase = Math.max(0, Math.min(cases.length-1, extState.gkCase + parseInt(t.dataset.delta)));
    renderExternal();
  }}
}}, true);
</script>
</body>
</html>'''

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 저장 완료: {out_path}")
    webbrowser.open(f"file://{out_path}")

if __name__ == "__main__":
    generate_html()
