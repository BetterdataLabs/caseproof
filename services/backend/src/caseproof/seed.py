"""Seed fictional organisations, identities and the published sample policy.

Run with the owner role (migrations/bootstrap only). Demo cases are created through the ordinary domain
commands with the runtime role, so they pass the same row policies and validations as any other case.
"""

from __future__ import annotations

import argparse
import shutil

from sqlalchemy import select, text

from .actors import Actor
from .catalog import sample_policy
from .config import get_settings
from .db import global_session, org_session, owner_engine
from .history import utcnow
from .models import ORG_SCOPED_TABLES, Membership, Organisation, OrgControl, PolicyVersion, User

ORGS = [
    {
        "slug": "straits",
        "name": "Straits Commercial Bank — Trade Operations",
        "short_name": "Straits Commercial",
    },
    {"slug": "lumen", "name": "Lumen Bank — Invoice Finance", "short_name": "Lumen Bank"},
]
PEOPLE = [
    (
        "dev:vendor",
        "Sam Lim",
        "sam.lim@vendor.example",
        "Vendor representative",
        "straits",
        ["vendor"],
    ),
    (
        "dev:alex",
        "Alex Chen",
        "alex.chen@straits.example",
        "Demo lead · combined roles for walkthroughs",
        "straits",
        ["reviewer", "supervisor", "simulation_operator", "environment_admin"],
    ),
    (
        "dev:priya",
        "Priya Raman",
        "priya.raman@straits.example",
        "Operations reviewer",
        "straits",
        ["reviewer"],
    ),
    (
        "dev:daniel",
        "Daniel Koh",
        "daniel.koh@straits.example",
        "Operations supervisor",
        "straits",
        ["supervisor", "reviewer"],
    ),
    ("dev:aisha", "Aisha Tan", "aisha.tan@straits.example", "Auditor", "straits", ["auditor"]),
    (
        "dev:sam",
        "Sam Lim",
        "sam.lim@straits.example",
        "Simulation operator (demo customer)",
        "straits",
        ["simulation_operator"],
    ),
    (
        "dev:morgan",
        "Morgan Ong",
        "morgan.ong@straits.example",
        "Environment administrator",
        "straits",
        ["environment_admin"],
    ),
    (
        "dev:wei",
        "Li Wei",
        "li.wei@lumen.example",
        "Operations reviewer",
        "lumen",
        ["reviewer", "supervisor", "simulation_operator"],
    ),
]
PUBLIC_PERSONAS = ("dev:alex", "dev:vendor", "dev:aisha")
DEMO_CASES = [("two-gaps", "autonomous"), ("disputed-receipt", "autonomous"), ("clean-case", "autonomous")]


def reset() -> None:
    engine = owner_engine()
    with engine.begin() as conn:
        tables = ", ".join(ORG_SCOPED_TABLES + ["memberships", "users", "organisations", "purge_records"])
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    storage = get_settings().storage_dir
    if storage.exists():
        shutil.rmtree(storage)


def seed_identities() -> dict[str, Organisation]:
    engine = owner_engine()
    orgs: dict[str, Organisation] = {}
    with global_session(engine) as session:
        for spec in ORGS:
            org = session.execute(
                select(Organisation).where(Organisation.slug == spec["slug"])
            ).scalar_one_or_none()
            if org is None:
                org = Organisation(**spec)
                session.add(org)
                session.flush()
            orgs[spec["slug"]] = org
            if session.get(OrgControl, org.id) is None:
                session.add(OrgControl(org_id=org.id, revision=1, automation_enabled=True))
            policy_def = sample_policy()
            exists = session.execute(
                select(PolicyVersion).where(
                    PolicyVersion.org_id == org.id,
                    PolicyVersion.key == policy_def["key"],
                    PolicyVersion.version == policy_def["version"],
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    PolicyVersion(
                        org_id=org.id,
                        key=policy_def["key"],
                        version=policy_def["version"],
                        name=policy_def["name"],
                        status="published",
                        definition=policy_def,
                        published_at=utcnow(),
                    )
                )
        for subject, name, email, title, org_slug, roles in PEOPLE:
            user = session.execute(select(User).where(User.subject == subject)).scalar_one_or_none()
            if user is None:
                user = User(subject=subject, email=email, display_name=name, title=title)
                session.add(user)
                session.flush()
            membership = session.execute(
                select(Membership).where(
                    Membership.user_id == user.id, Membership.org_id == orgs[org_slug].id
                )
            ).scalar_one_or_none()
            if membership is None:
                session.add(Membership(org_id=orgs[org_slug].id, user_id=user.id, roles=roles))
    return orgs


def seed_demo_cases(orgs: dict[str, Organisation]) -> list[str]:
    from .casework import create_case, settle_execution
    from .jobs import enqueue_agent

    created = []
    with global_session(owner_engine()) as session:
        users = {u.subject: u for u in session.execute(select(User)).scalars()}
    for slug, cases in (("straits", DEMO_CASES), ("lumen", [("clean-case", "autonomous")])):
        org = orgs[slug]
        lead = users["dev:alex" if slug == "straits" else "dev:wei"]
        actor = Actor(
            "person",
            f"user:{lead.id}",
            lead.display_name,
            org.id,
            frozenset({"reviewer", "supervisor"}),
            lead.id,
        )
        for scenario_key, mode in cases:
            with org_session(org.id) as session:
                policy = (
                    session.execute(select(PolicyVersion).where(PolicyVersion.status == "published"))
                    .scalars()
                    .first()
                )
                case = create_case(
                    session,
                    actor,
                    policy=policy,
                    scenario_key=scenario_key,
                    assigned_to=lead.id,
                    automation_mode=mode,
                )
                enqueue_agent(session, case, "CaseCreated", "seeded demonstration case")
                settle_execution(session, case)
                created.append(f"{slug}:{case.reference}:{scenario_key}")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CaseProof fictional data")
    parser.add_argument("--reset", action="store_true", help="Remove all data and stored objects first")
    parser.add_argument(
        "--demo-cases", action="store_true", help="Create demonstration cases (queued for the agent)"
    )
    parser.add_argument(
        "--iap-user",
        action="append",
        default=[],
        help="email=role1,role2 — grant a verified IAP identity membership of the demo organisation",
    )
    args = parser.parse_args()
    if args.reset:
        reset()
    orgs = seed_identities()
    print("organisations:", ", ".join(o.short_name for o in orgs.values()))
    for spec in args.iap_user:
        email, _, roles = spec.partition("=")
        with global_session(owner_engine()) as session:
            subject = f"iap:{email.strip().lower()}"
            user = session.execute(select(User).where(User.subject == subject)).scalar_one_or_none()
            if user is None:
                user = User(
                    subject=subject,
                    email=email.strip(),
                    display_name=email.split("@")[0].replace(".", " ").title(),
                    title="Invited reviewer",
                )
                session.add(user)
                session.flush()
            if session.execute(select(Membership).where(Membership.user_id == user.id)).first() is None:
                session.add(
                    Membership(
                        org_id=orgs["straits"].id,
                        user_id=user.id,
                        roles=[r.strip() for r in (roles or "reviewer").split(",")],
                    )
                )
        print("iap member", email)
    if args.demo_cases:
        for line in seed_demo_cases(orgs):
            print("case", line)


if __name__ == "__main__":
    main()
