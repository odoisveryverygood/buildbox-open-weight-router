"""Explicit interactive setup for one operator identity; never creates provider keys."""

import argparse
import getpass
import json
import os
import secrets

from buildbox_router.auth import Identity, password_hash


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    password = getpass.getpass("New planning password (not echoed): ")
    if len(password) < 16 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords must match and contain at least 16 characters")
    salt = secrets.token_hex(16)
    identity = Identity(
        username=args.username,
        owner=args.owner,
        salt=salt,
        password_hash=password_hash(password, salt),
    )
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps([identity.model_dump()]) + "\n")
    print("Created private authentication file. No password or provider credential was printed.")


if __name__ == "__main__":
    main()
