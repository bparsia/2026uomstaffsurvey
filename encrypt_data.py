"""
Bundle data/ into a single encrypted blob (data.enc) safe to commit to a
public GitHub repo. Run this after extract.py whenever the CSVs change.

Requires DATA_KEY in .streamlit/secrets.toml (a Fernet key — generate one
with `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and set the same value in the Streamlit Cloud app's secrets dashboard).

data/*.csv themselves are gitignored — only data.enc is committed. The app
decrypts data.enc back into data/ at startup via utils.ensure_data_decrypted().
"""
import io
import tarfile
import tomllib
from pathlib import Path

from cryptography.fernet import Fernet

DATA_DIR = Path("data")
OUT = Path("data.enc")
SECRETS_PATH = Path(".streamlit/secrets.toml")


def load_key() -> bytes:
    if not SECRETS_PATH.exists():
        raise SystemExit(
            f"{SECRETS_PATH} not found. Create it with a DATA_KEY — generate one with:\n"
            '  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    secrets = tomllib.loads(SECRETS_PATH.read_text())
    key = secrets.get("DATA_KEY")
    if not key:
        raise SystemExit(f"DATA_KEY not set in {SECRETS_PATH}")
    return key.encode()


def main():
    key = load_key()
    fernet = Fernet(key)

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for csv_path in sorted(DATA_DIR.glob("*.csv")):
            tar.add(csv_path, arcname=csv_path.name)

    encrypted = fernet.encrypt(buf.getvalue())
    OUT.write_bytes(encrypted)
    print(f"{OUT}: {len(encrypted):,} bytes (from {buf.tell():,} bytes uncompressed tar)")


if __name__ == "__main__":
    main()
