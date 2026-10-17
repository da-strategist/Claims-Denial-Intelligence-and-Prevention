"""Manage organisations (each one's data is kept apart from the others').

    uv run python -m app.orgs list
    uv run python -m app.orgs migrate                     # one-time: today's data -> "meridian"
    uv run python -m app.orgs add-sample                  # the synthetic "lakeside" practice
    uv run python -m app.orgs add acme --name "Acme Health" --data-dir /path/to/acme/csvs

`migrate` moves a single-organisation install's files into backend/orgs/meridian/ and
assigns every account without an organisation to it. It never overwrites a file and is
safe to run twice. Accounts are then added to an organisation with
`python -m app.users add … --org <id>`.
"""

import argparse
import os
import sys
from pathlib import Path

from app.data.corrections import DEFAULT_CORRECTIONS_FILE
from app.data.drafts import DEFAULT_DRAFTS_FILE
from app.data.new_claims import DEFAULT_NEW_CLAIMS_FILE
from app.data.orgs import get_org_registry
from app.data.registrations import DEFAULT_REGISTRATIONS_FILE
from app.data.repository import DEFAULT_DATA_DIR
from app.data.rules import DEFAULT_RULES_FILE
from app.data.users import get_user_store
from app.sample_org import generate
from app.services.edi_settings import DEFAULT_EDI_SETTINGS_FILE

FIRST_ORG = ("meridian", "Meridian Regional Medical Center")
SAMPLE_ORG = ("lakeside", "Lakeside Family Practice")
LEGACY_AUDIT_FILE = Path(__file__).resolve().parents[1] / "logs" / "audit.jsonl"

# Where a single-organisation install kept each file -> its name in the organisation folder
LEGACY_FILES = [
    (DEFAULT_RULES_FILE, "rules.json"),
    (DEFAULT_CORRECTIONS_FILE, "claim_corrections.json"),
    (DEFAULT_DRAFTS_FILE, "claim_drafts.json"),
    (DEFAULT_NEW_CLAIMS_FILE, "new_claims.json"),
    (DEFAULT_REGISTRATIONS_FILE, "patient_registrations.json"),
    (DEFAULT_EDI_SETTINGS_FILE, "edi_settings.json"),
    (LEGACY_AUDIT_FILE, "logs/audit.jsonl"),
]


def migrate() -> list[str]:
    """Move today's single-organisation data into the first organisation. Returns what it did."""
    registry = get_org_registry()
    org_id, name = FIRST_ORG
    done = []
    if registry.get(org_id) is None:
        data_dir = Path(os.path.relpath(DEFAULT_DATA_DIR, registry.root))
        registry.add(org_id, name, data_dir)
        done.append(f"created organisation {org_id} ({name}), claims data {DEFAULT_DATA_DIR}")
    folder = registry.folder(org_id)
    for old, new_name in LEGACY_FILES:
        new = folder / new_name
        if old.exists() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            old.replace(new)  # same disk: a move, so permissions and the audit chain are kept
            done.append(f"moved {old.name} -> orgs/{org_id}/{new_name}")
        elif old.exists():
            done.append(f"left {old} in place: orgs/{org_id}/{new_name} already exists")
    users = get_user_store()
    for user in users.list():
        if user.organisation_id is None:
            users.update(user.username, organisation_id=org_id)
            done.append(f"assigned {user.username} to {org_id}")
    return done


def add_sample() -> str:
    registry = get_org_registry()
    org_id, name = SAMPLE_ORG
    if registry.get(org_id) is not None:
        return f"{org_id} already exists"
    if registry.get(FIRST_ORG[0]) is None:
        raise LookupError("Run `python -m app.orgs migrate` first (the sample copies its code sets)")
    data_dir = registry.folder(org_id) / "data"
    generate(data_dir, registry.data_dir(FIRST_ORG[0]))
    registry.add(org_id, name, Path(org_id) / "data")
    return f"created organisation {org_id} ({name}) with sample data in orgs/{org_id}/data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage organisations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="show organisations")
    commands.add_parser("migrate", help="move a single-organisation install into 'meridian'")
    commands.add_parser("add-sample", help="add the synthetic Lakeside Family Practice")
    add = commands.add_parser("add", help="add an organisation")
    add.add_argument("org_id")
    add.add_argument("--name", required=True)
    add.add_argument("--data-dir", required=True, help="folder with the organisation's claims CSVs")
    args = parser.parse_args(argv)
    registry = get_org_registry()
    try:
        match args.command:
            case "list":
                for org in registry.list():
                    accounts = sum(1 for u in get_user_store().list() if u.organisation_id == org.id)
                    print(f"{org.id:14} {org.status:10} {accounts:3} accounts  {org.name}")
            case "migrate":
                for line in migrate() or ["nothing to do"]:
                    print(line)
            case "add-sample":
                print(add_sample())
            case "add":
                org = registry.add(args.org_id, args.name, Path(args.data_dir).resolve())
                print(f"created organisation {org.id} ({org.name})")
    except (ValueError, LookupError) as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
