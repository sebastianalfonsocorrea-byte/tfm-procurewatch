from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import Agent2Contract, Agent2Score


@dataclass
class Agent2State:
    contracts: list[Agent2Contract] = field(default_factory=list)
    scores: list[Agent2Score] = field(default_factory=list)
