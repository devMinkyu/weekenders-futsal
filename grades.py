#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 선수별 세부 능력치 — 데이터는 grades.json 에 있습니다.
#
# ※ 등급 데이터 수정은 grades.json 을 고치세요 (봇도 json 만 수정).
#    이 파일(.py)은 점수 계산 로직·검증만 담당합니다.
#
# 각 항목 등급: A / B / C / D   (A=4, B=3, C=2, D=1)
# 합산점수는 ABILITY_KEYS 의 항목들을 더해 자동 계산됩니다.
# 용병(미등록 선수)·값이 빠진 항목은 자동으로 B 등급 처리됩니다.
#
# ── 항목을 추가/변경하려면? ──────────────────────────────────────
#   ABILITY_KEYS 에 항목명을 추가/수정하면 됩니다.
#   grades.json 의 각 선수에 해당 항목을 넣으면 반영, 안 넣으면 기본값(B).

import json
from pathlib import Path

# 평가 항목 (이 리스트가 점수 계산의 기준)
ABILITY_KEYS = ["패스", "리턴", "수비", "드리블", "볼소유", "골결정력"]

# 등급 → 점수
ABILITY_SCORE = {"A": 4, "B": 3, "C": 2, "D": 1}

MERCENARY_GRADE = "B"  # 미등록 선수·빠진 항목 기본 등급

GRADES_FILE = Path(__file__).parent / "grades.json"


def _load_abilities() -> dict:
    try:
        return json.loads(GRADES_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"grades.json 형식 오류: {e}")


# 선수별 세부 등급 {선수명: {항목명: 등급}}
PLAYER_ABILITIES = _load_abilities()


def player_score(name: str) -> int:
    """ABILITY_KEYS 기준으로 세부 등급을 합산해 점수를 계산.
    미등록 선수나 빠진 항목은 MERCENARY_GRADE(B) 로 간주."""
    abilities = PLAYER_ABILITIES.get(name, {})
    default = ABILITY_SCORE[MERCENARY_GRADE]
    return sum(ABILITY_SCORE.get(abilities.get(key), default) for key in ABILITY_KEYS)


def _validate() -> None:
    """로드 시 자동 검증: 오타난 등급·존재하지 않는 항목이 있으면 즉시 에러."""
    valid_grades = set(ABILITY_SCORE)       # {"A","B","C","D"}
    valid_keys = set(ABILITY_KEYS)
    errors = []
    for name, ab in PLAYER_ABILITIES.items():
        if not isinstance(ab, dict):
            errors.append(f"'{name}' 능력치는 딕셔너리여야 해요: {ab!r}")
            continue
        for key, grade in ab.items():
            if key not in valid_keys:
                errors.append(f"'{name}' 알 수 없는 항목 '{key}' (ABILITY_KEYS: {ABILITY_KEYS})")
            if grade not in valid_grades:
                errors.append(f"'{name}' '{key}' 잘못된 등급 '{grade}' (가능: A/B/C/D)")
    if MERCENARY_GRADE not in valid_grades:
        errors.append(f"MERCENARY_GRADE '{MERCENARY_GRADE}' 가 A/B/C/D 중에 없어요")
    if errors:
        raise ValueError("grades.json 등급 데이터 오류:\n  - " + "\n  - ".join(errors))


_validate()  # import 되는 순간 검증
