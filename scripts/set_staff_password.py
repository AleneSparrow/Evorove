"""Set a new password for an existing evorove.com staff account, directly in
the database -- for when the password-reset email cannot be delivered
(Railway Hobby blocks outbound SMTP, so /forgot-password never sends).

Run it yourself from the repo root, with Railway's DATABASE_URL injected:

    cd ~/dev/evorove
    railway link            # once: project prolific-clarity, service ai-business-process-engine
    railway run python scripts/set_staff_password.py alenesparrowvn@gmail.com

The password is typed into a hidden prompt (getpass): it is never printed,
logged, or passed on the command line. Minimum 12 characters (same rule as
the site). All existing sessions of that account are left as they are.
"""

from __future__ import annotations

import dataclasses
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domain.auth import hash_password, normalize_email  # noqa: E402
from src.persistence.sqlalchemy_uow import (  # noqa: E402
    SQLAlchemyUnitOfWork,
    create_database_engine,
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/set_staff_password.py <email>")
    email = normalize_email(sys.argv[1])

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set -- run this through `railway run`.")

    first = getpass.getpass("New password (min 12 chars): ")
    second = getpass.getpass("Repeat new password: ")
    if first != second:
        raise SystemExit("Passwords do not match. Nothing changed.")
    try:
        new_hash = hash_password(first)
    except ValueError as exc:
        raise SystemExit(f"Rejected: {exc}. Nothing changed.")

    engine = create_database_engine(database_url)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    with factory() as uow:
        user = uow.staff_users.get_by_email(email, for_update=True)
        if user is None:
            raise SystemExit(f"No account with email {email!r}. Nothing changed.")
        uow.staff_users.save(dataclasses.replace(user, password_hash=new_hash))
        uow.commit()
    print(f"Password updated for {email}. Sign in at https://evorove.com/login")


if __name__ == "__main__":
    main()
