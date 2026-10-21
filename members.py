#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 이번 주 참여 멤버 — 매주 여기만 수정하세요

from enum import Enum

class Mode(Enum):
    AUTO  = "auto"
    MATCH = "match"
    SELF  = "self"

GAME_MODE = Mode.AUTO

# 14명 자체전일 때 7:7(벤치 0)로 진행. False면 기본 6:6(벤치 2명 로테이션)
SEVEN_V_SEVEN = False

# 같은 팀으로 묶기: 각 쌍(튜플) 선수들이 무조건 같은 팀  예) [("김민규", "이성학")]
FIXED_SAME_TEAM = []
# 다른 팀으로 분리: 각 쌍(튜플)의 두 선수가 무조건 다른 팀  예) [("박현욱", "박현성")]
FIXED_DIFF_TEAM = []

MEMBERS = [
    "김민규",
    "박현성",
    "박현욱",
    "이성학",
    "오영웅",
    "정준영",
    "김현준",
    "김동호",
    "김태균",
    "박찬형",
    "김재혁",
    "박상익",
]
