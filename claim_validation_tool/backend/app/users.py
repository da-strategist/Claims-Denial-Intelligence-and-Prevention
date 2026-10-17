"""Manage sign-in accounts. Passwords are typed at a hidden prompt, never on the command line.

    uv run python -m app.users add alice --name "Alice Jones" --role admin
    uv run python -m app.users list
    uv run python -m app.users password alice
    uv run python -m app.users role alice biller
    uv run python -m app.users disable alice      # signs them out on their next request
    uv run python -m app.users enable alice

Roles: analyst (claims and dashboards, no patient details), biller (also patient details and
changing claims), admin (also validation rules and the audit log).
"""

import argparse
import getpass
import sys

from app.data.users import get_user_store
from app.models import Role


def _new_password() -> str:
    password = getpass.getpass("New password: ")
    if getpass.getpass("Repeat it: ") != password:
        raise ValueError("The passwords don't match")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage sign-in accounts")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="create an account")
    add.add_argument("username")
    add.add_argument("--name", help="display name (defaults to the username)")
    add.add_argument("--role", type=Role, choices=list(Role), required=True)
    commands.add_parser("list", help="show accounts")
    for name, text in [
        ("password", "set a new password"),
        ("disable", "block sign-in"),
        ("enable", "allow sign-in again"),
    ]:
        commands.add_parser(name, help=text).add_argument("username")
    role = commands.add_parser("role", help="change an account's role")
    role.add_argument("username")
    role.add_argument("role", type=Role, choices=list(Role))
    args = parser.parse_args(argv)

    users = get_user_store()
    try:
        match args.command:
            case "add":
                user = users.add(args.username, args.name or args.username, args.role, _new_password())
                print(f"Created {user.username} ({user.role})")
            case "list":
                for user in users.list():
                    state = "active" if user.active else "disabled"
                    print(f"{user.username:20} {user.role:8} {state:9} {user.display_name}")
            case "password":
                users.update(args.username, password=_new_password())
                print(f"Password changed for {args.username}")
            case "role":
                users.update(args.username, role=args.role)
                print(f"{args.username} is now {args.role}")
            case "disable" | "enable":
                users.update(args.username, active=args.command == "enable")
                print(f"{args.username} {args.command}d")
    except (ValueError, LookupError) as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
