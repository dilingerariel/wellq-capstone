"""Generate a scrypt hash for WELLQ_PLATFORM_ADMIN_PASSWORD_HASH."""
import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.account_auth import hash_password


def main() -> None:
    password = getpass.getpass("New platform admin password (input hidden): ")
    confirmation = getpass.getpass("Confirm password (input hidden): ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if not 12 <= len(password) <= 128:
        raise SystemExit("Password must contain 12-128 characters. Run the command again.")
    print("Set this output as the Vercel secret WELLQ_PLATFORM_ADMIN_PASSWORD_HASH:")
    print(hash_password(password))


if __name__ == "__main__":
    main()
