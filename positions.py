#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 선수별 포지션 — 데이터는 positions.json 에 있습니다.
#
# ※ 포지션 데이터 수정은 positions.json 을 고치세요 (봇도 json 만 수정).
#    이 파일(.py)은 포지션 구성 상수만 담당합니다.
#
# 포지션 종류:
#   ST : 공격수 / CM : 중앙 미드필더 / RB : 오른쪽 수비 / LB : 왼쪽 수비 / CB : 중앙 수비수
#
# json 형식: "선수명": ["1순위", "2순위"]
# ※ 같은 팀 내 1순위 포지션이 겹칠 경우, 등급이 높은 선수가 2순위로 이동합니다

import json
from pathlib import Path

POSITIONS_FILE = Path(__file__).parent / "positions.json"


def _load_positions() -> dict:
    try:
        raw = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"positions.json 형식 오류: {e}")
    # JSON 리스트 → 튜플 (기존 코드 호환)
    return {name: tuple(pos) for name, pos in raw.items()}


# 선수별 포지션 {선수명: ("1순위", "2순위")}
PLAYER_POSITIONS = _load_positions()

# 인원수별 이상적인 필드 포지션 구성 (GK 제외)
# 5인제: GK 1명 + 필드 4명 → CM 없이 운영
# 6인제: GK 1명 + 필드 5명 → CM 포함
# 7인제: GK 1명 + 필드 6명 → CM 2명 (중앙 좌/우), 14명 자체전 7:7 전용
IDEAL_POSITIONS_5 = ["ST", "RB", "LB", "CB"]              # 5인제 (GK 제외 4자리, CM 없음)
IDEAL_POSITIONS_6 = ["ST", "CM", "RB", "LB", "CB"]        # 6인제 (GK 제외 5자리)
IDEAL_POSITIONS_7 = ["ST", "CM", "CM", "RB", "LB", "CB"]  # 7인제 (GK 제외 6자리, CM 2명)

# 하위 호환
IDEAL_POSITIONS = IDEAL_POSITIONS_5
