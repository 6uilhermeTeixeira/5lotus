"""Generate a scrypt value for DAYTRADE_DASHBOARD_PASSWORD without storing the password."""

import getpass
import hashlib
import secrets


def main() -> None:
    password = getpass.getpass("Dashboard password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()
    print(f"scrypt${salt.hex()}${digest}")


if __name__ == "__main__":
    main()
