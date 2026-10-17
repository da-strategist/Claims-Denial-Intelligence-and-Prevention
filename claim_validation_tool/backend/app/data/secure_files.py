"""Encryption at rest for each organisation's patient data (envelope encryption).

A master key (RCM_MASTER_KEY, a Fernet key kept outside the data folders: in .env now, a
cloud key service at go-live) wraps one data key per organisation, saved wrapped in
orgs/<id>/data_key.enc. That data key encrypts the organisation's files holding PHI:
new claims, drafts, corrections, patient registrations, its audit log (line by line), and
the CSVs in its own data folder (saved as <name>.csv.enc).

- Without a master key everything is read and written as plain text (development and
  tests); RCM_ENVIRONMENT=production refuses to start without one (main.py).
- Reads accept plain or encrypted content, so files can be encrypted where they are
  (`python -m app.orgs encrypt`) and nothing breaks halfway.
- Deleting an organisation's data key makes any copy of its encrypted files unreadable
  (crypto-shredding), including copies in backups.
- Several master keys may be given, comma-separated: the first wraps new data keys, the
  rest still unwrap older ones. To retire an old master key, put the new one first, run
  `python -m app.orgs rotate-key` (re-wraps every data key with it), then remove the old.

Settings without PHI (rules.json, edi_settings.json) stay plain text so they can be read
and reviewed.
"""

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

MASTER_KEY_ENV = "RCM_MASTER_KEY"
ENVIRONMENT_ENV = "RCM_ENVIRONMENT"
DATA_KEY_FILE = "data_key.enc"
ENCRYPTED_SUFFIX = ".enc"
_TOKEN_PREFIX = b"gAAAAA"
_KEY_LOCK = Lock()  # one data key per organisation, even when first requests arrive together  # every Fernet token starts with this (version byte + timestamp)


class EncryptionError(RuntimeError):
    """Encrypted data that can't be read: no master key, or the wrong one."""


def production() -> bool:
    return os.environ.get(ENVIRONMENT_ENV, "").strip().lower() == "production"


def new_master_key() -> str:
    return Fernet.generate_key().decode()


def master_key() -> MultiFernet | None:
    raw = os.environ.get(MASTER_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        return MultiFernet([Fernet(k.strip()) for k in raw.split(",") if k.strip()])
    except ValueError as err:
        raise EncryptionError(f"{MASTER_KEY_ENV} is not a valid key: {err}") from None


def is_encrypted(data: bytes | str) -> bool:
    if isinstance(data, str):
        data = data.encode()
    return data.lstrip().startswith(_TOKEN_PREFIX)


@lru_cache(maxsize=None)
def org_cipher(folder: Path) -> Fernet | None:
    """The data key of the organisation whose app-data folder this is (created on first
    use), or None without a master key."""
    master = master_key()
    key_file = folder / DATA_KEY_FILE
    if master is None:
        if key_file.exists():
            raise EncryptionError(
                f"{folder.name}'s data is encrypted; set {MASTER_KEY_ENV} to read it"
            )
        return None
    with _KEY_LOCK:
        if not key_file.exists():
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                # O_EXCL: never replace a key another process has just created
                fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(master.encrypt(Fernet.generate_key()))
            except FileExistsError:
                pass
    return Fernet(_unwrap(master, key_file))


def _unwrap(master: MultiFernet, key_file: Path) -> bytes:
    try:
        return master.decrypt(key_file.read_bytes())
    except InvalidToken:
        raise EncryptionError(
            f"{MASTER_KEY_ENV} doesn't unlock {key_file.parent.name}'s data key"
        ) from None


def rewrap_data_key(folder: Path) -> bool:
    """Re-wrap the organisation's data key with the first master key. The data key itself,
    and so every encrypted file, is unchanged. False if there's no key or it already was."""
    master = master_key()
    if master is None:
        raise EncryptionError(f"Set {MASTER_KEY_ENV} first")
    key_file = folder / DATA_KEY_FILE
    if not key_file.exists():
        return False
    data_key = _unwrap(master, key_file)
    primary = Fernet(os.environ[MASTER_KEY_ENV].split(",")[0].strip())
    try:
        if primary.decrypt(key_file.read_bytes()) == data_key:
            return False
    except InvalidToken:
        pass
    write_bytes(key_file, primary.encrypt(data_key))
    org_cipher.cache_clear()
    return True


def shred(folder: Path) -> bool:
    """Destroy the organisation's data key: its encrypted files can never be read again."""
    org_cipher.cache_clear()
    key_file = folder / DATA_KEY_FILE
    if not key_file.exists():
        return False
    key_file.unlink()
    return True


def _decrypt(data: bytes, cipher: Fernet | None, where: Path) -> bytes:
    if not is_encrypted(data):
        return data
    if cipher is None:
        raise EncryptionError(f"{where.name} is encrypted; set {MASTER_KEY_ENV} to read it")
    try:
        return cipher.decrypt(data.strip())
    except InvalidToken:
        raise EncryptionError(f"{where.name} can't be decrypted with this key") from None


def write_bytes(path: Path, data: bytes) -> None:
    """Atomically, readable only by the account running the API."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    tmp.replace(path)


def read_text(path: Path, cipher: Fernet | None) -> str:
    return _decrypt(path.read_bytes(), cipher, path).decode()


def write_text(path: Path, text: str, cipher: Fernet | None) -> None:
    data = text.encode()
    write_bytes(path, cipher.encrypt(data) if cipher else data)


def append_line(path: Path, line: str, cipher: Fernet | None) -> None:
    """One line, encrypted on its own so the file can still be appended to."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = cipher.encrypt(line.encode()).decode() if cipher else line
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(data + "\n")


def iter_lines(path: Path, cipher: Fernet | None) -> Iterator[str]:
    with path.open("rb") as f:
        for raw in f:
            if raw.strip():
                yield _decrypt(raw, cipher, path).decode().rstrip("\n")


def encrypt_file(path: Path, cipher: Fernet, *, by_line: bool = False) -> bool:
    """Encrypt a plain-text file in place; False if it already was."""
    data = path.read_bytes()
    if by_line:
        lines = [line for line in data.splitlines() if line.strip()]
        if all(is_encrypted(line) for line in lines):
            return False
        out = b"".join(
            (line if is_encrypted(line) else cipher.encrypt(line)) + b"\n" for line in lines
        )
        write_bytes(path, out)
        return True
    if is_encrypted(data):
        return False
    write_bytes(path, cipher.encrypt(data))
    return True


def table_path(data_dir: Path, name: str) -> Path:
    """The table's file: <name>.csv.enc if it's been encrypted, else <name>.csv."""
    encrypted = data_dir / f"{name}.csv{ENCRYPTED_SUFFIX}"
    return encrypted if encrypted.exists() else data_dir / f"{name}.csv"
