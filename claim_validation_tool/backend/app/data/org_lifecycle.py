"""An organisation's data over its life: encrypting it where it is, exporting it (e.g. when
it leaves), and deleting it for good.

    encrypt_organisation  turn on encryption at rest for files written before it was on
    export_organisation   one zip with everything the organisation has here, decrypted
    delete_organisation   destroy its data key, delete its folder and accounts

Settings without PHI (rules.json, edi_settings.json) are exported but never encrypted. A
claims data folder outside the organisation's own folder (e.g. Meridian's Data/raw_data)
is the organisation's source system, not a copy we own: it is exported but never encrypted
or deleted here, and both say so.
"""

import hashlib
import io
import json
import shutil
import zipfile
from datetime import UTC, datetime

from app.data.emergency import get_emergency_access
from app.data.orgs import OrgStatus, get_org_registry, org_cipher_for
from app.data.secure_files import (
    ENCRYPTED_SUFFIX,
    EncryptionError,
    encrypt_file,
    rewrap_data_key,
    iter_lines,
    read_text,
    shred,
    table_path,
    write_bytes,
)
from app.data.users import get_user_store
from app.sample_org import ORGANISATION_TABLES  # its own tables; the code sets are shared

# The organisation's files holding PHI, encrypted when encryption is on
PHI_FILES = [
    "new_claims.json",
    "claim_drafts.json",
    "claim_corrections.json",
    "patient_registrations.json",
]
AUDIT_FILE = "logs/audit.jsonl"  # encrypted line by line
SETTINGS_FILES = ["rules.json", "edi_settings.json"]



def owns_data_dir(org_id: str) -> bool:
    """Whether the claims data folder is inside the organisation's own folder."""
    registry = get_org_registry()
    return registry.data_dir(org_id).resolve().is_relative_to(registry.folder(org_id).resolve())


def encrypt_organisation(org_id: str) -> list[str]:
    """Encrypt the organisation's existing files in place. Safe to run twice."""
    cipher = org_cipher_for(org_id)
    if cipher is None:
        raise EncryptionError("Set RCM_MASTER_KEY first (`python -m app.orgs new-master-key`)")
    registry = get_org_registry()
    folder, done = registry.folder(org_id), []
    for name in PHI_FILES + [AUDIT_FILE]:
        path = folder / name
        if path.exists() and encrypt_file(path, cipher, by_line=name == AUDIT_FILE):
            done.append(f"encrypted {org_id}/{name}")
    data_dir = registry.data_dir(org_id)
    if not owns_data_dir(org_id):
        done.append(f"left {data_dir} as it is: it's outside {org_id}'s folder")
        return done
    for table in ORGANISATION_TABLES:
        plain = data_dir / f"{table}.csv"
        if plain.exists():
            encrypted = plain.with_name(plain.name + ENCRYPTED_SUFFIX)
            write_bytes(encrypted, cipher.encrypt(plain.read_bytes()))
            plain.unlink()
            done.append(f"encrypted {table}.csv -> {table}.csv{ENCRYPTED_SUFFIX}")
    return done


def export_organisation(org_id: str, exported_by: str) -> tuple[bytes, dict]:
    """A zip of the organisation's data, decrypted, with a manifest (each file's size and
    SHA-256) so the recipient can check nothing was lost. Returns (zip, manifest)."""
    registry = get_org_registry()
    org = registry.get(org_id)
    folder, data_dir = registry.folder(org_id), registry.data_dir(org_id)
    cipher = org_cipher_for(org_id)
    files: dict[str, bytes] = {}
    for name in SETTINGS_FILES + PHI_FILES:
        path = folder / name
        if path.exists():
            files[f"app/{name}"] = read_text(path, cipher).encode()
    audit = folder / AUDIT_FILE
    if audit.exists():
        files["app/audit.jsonl"] = "".join(line + "\n" for line in iter_lines(audit, cipher)).encode()
    for table in ORGANISATION_TABLES:
        path = table_path(data_dir, table)
        if path.exists():
            text = read_text(path, cipher) if path.suffix == ENCRYPTED_SUFFIX else path.read_text()
            files[f"data/{table}.csv"] = text.encode()
    accounts = [
        u.model_dump(mode="json", include={"username", "display_name", "role", "active", "scope", "created_at"})
        for u in get_user_store().list()
        if u.organisation_id == org_id
    ]
    files["accounts.json"] = json.dumps(accounts, indent=2).encode()
    manifest = {
        "organisation": {"id": org.id, "name": org.name},
        "exported_at": datetime.now(UTC).isoformat(),
        "exported_by": exported_by,
        "note": "Decrypted copy of everything this organisation has in ClaustraRCM. It holds PHI: "
        "store and send it only as your HIPAA policies allow. Passwords are not included.",
        "files": [
            {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for path, data in files.items()
        ],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for path, data in files.items():
            zf.writestr(path, data)
    return buffer.getvalue(), manifest


def delete_organisation(org_id: str, by: str = "platform") -> list[str]:
    """Delete a suspended organisation for good: its data key first (so any copy of its
    encrypted files, backups included, is unreadable), then its folder and accounts. The
    registry keeps a record that it existed, so its ID is never reused."""
    registry = get_org_registry()
    org = registry.get(org_id)
    if org is None:
        raise LookupError(f"No organisation {org_id}")
    if org.status != OrgStatus.SUSPENDED:
        raise ValueError("Suspend the organisation before deleting it")
    folder, data_dir = registry.folder(org_id), registry.data_dir(org_id)
    external = not owns_data_dir(org_id)
    done = []
    ended = get_emergency_access().end_for_organisation(org_id, by)
    if ended:
        done.append(f"ended {len(ended)} open emergency access grant(s)")
    if shred(folder):
        done.append("destroyed its data key: encrypted copies anywhere can't be read")
    if folder.exists():
        shutil.rmtree(folder)
        done.append(f"deleted its folder ({folder.name}/)")
    users = get_user_store()
    members = [u.username for u in users.list() if u.organisation_id == org_id]
    users.remove(members)
    done.append(f"deleted {len(members)} account(s)")
    if external:
        done.append(f"did not delete {data_dir}: it's outside the organisation's folder")
    registry.mark_deleted(org_id)
    return done


def rotate_master_key(org_id: str) -> bool:
    """Re-lock the organisation's data key with the first master key in RCM_MASTER_KEY, so
    older master keys can then be removed. False if it already was."""
    registry = get_org_registry()
    if not registry.has_data(org_id):
        raise LookupError(f"No organisation {org_id}")
    return rewrap_data_key(registry.folder(org_id))
