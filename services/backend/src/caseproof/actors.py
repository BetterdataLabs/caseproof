"""Who is acting. Identity comes from the server (session or IAP assertion), never from a request body."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

ROLE_REVIEWER = "reviewer"
ROLE_SUPERVISOR = "supervisor"
ROLE_AUDITOR = "auditor"
ROLE_ADMIN = "environment_admin"
ROLE_SIMULATION = "simulation_operator"
ROLE_VENDOR = "vendor"
ALL_ROLES = [ROLE_REVIEWER, ROLE_SUPERVISOR, ROLE_AUDITOR, ROLE_ADMIN, ROLE_SIMULATION, ROLE_VENDOR]


@dataclass(frozen=True)
class Actor:
    type: str  # person | agent | policy | system | simulation
    id: str
    name: str
    org_id: uuid.UUID
    roles: frozenset[str] = field(default_factory=frozenset)
    user_id: uuid.UUID | None = None

    def has(self, *roles: str) -> bool:
        return any(role in self.roles for role in roles)

    @property
    def workspace(self) -> str:
        if self.has(ROLE_REVIEWER, ROLE_SUPERVISOR, ROLE_ADMIN, ROLE_SIMULATION):
            return "bank"
        if self.has(ROLE_AUDITOR):
            return "viewer"
        return "vendor" if self.has(ROLE_VENDOR) else "viewer"


def agent_actor(org_id: uuid.UUID, controller: str = "adk-gemini") -> Actor:
    return Actor("agent", f"agent:{controller}", "CaseProof agent", org_id)


def system_actor(org_id: uuid.UUID, name: str = "Policy timer") -> Actor:
    return Actor("policy", "system:policy", name, org_id)


def simulation_actor(org_id: uuid.UUID, party_name: str) -> Actor:
    return Actor("simulation", "simulation:customer", party_name, org_id)
