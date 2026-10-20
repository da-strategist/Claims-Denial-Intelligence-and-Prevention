"""Manage accounts from the command line.

    python -m backend.app.users add admin@example.com --role platform_admin
    python -m backend.app.users add person@example.com            # individual
    python -m backend.app.users reset-password member@example.com
    python -m backend.app.users disable member@example.com
    python -m backend.app.users list

New accounts and resets get a generated temporary password, printed once;
the user must change it at first sign-in.
"""

import argparse
import secrets
import sys

from .auth.users import Role, user_store


def _temporary_password() -> str:
    return secrets.token_urlsafe(12)  # 16 characters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.users")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="create an account")
    add.add_argument("username")
    add.add_argument("--role", choices=[r.value for r in Role], default=Role.INDIVIDUAL.value)
    add.add_argument("--org", help="organisation ID (hospital roles; normally created in the app)")
    for name in ("reset-password", "disable", "enable"):
        sub.add_parser(name).add_argument("username")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    try:
        if args.command == "add":
            password = _temporary_password()
            user = user_store.create(args.username, password, Role(args.role), args.org)
            print(f"Created {user.role.value} {user.username}")
            print(f"Temporary password (shown once, must be changed at sign-in): {password}")
        elif args.command == "reset-password":
            password = _temporary_password()
            user_store.update(args.username, password=password, must_change_password=True)
            print(f"Temporary password (shown once, must be changed at sign-in): {password}")
        elif args.command in ("disable", "enable"):
            user_store.update(args.username, disabled=args.command == "disable")
            print(f"{args.username} {args.command}d")
        else:
            for u in user_store.all():
                flags = " (disabled)" if u.disabled else ""
                print(f"{u.role.value:<15} {u.username}{flags}  org: {u.org_id or '-'}")
    except (ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
