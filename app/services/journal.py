"""Durable batch recovery. No message bodies or credentials are stored."""
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


def validate_batch(batch):
    from app.rules.validation import validate_options, validate_rule
    try:
        if not isinstance(batch, dict) or batch.get("version") != 1:
            raise ValueError()
        if not isinstance(batch["batch_id"], str) or not batch["batch_id"]:
            raise ValueError()
        updates = batch["settings_update"]
        if not isinstance(updates, dict) or set(updates) - {"sift_mode", "last_sift_at", "last_sift_ids"}:
            raise ValueError()
        validate_options(updates)
        records = batch["records"]
        if not isinstance(records, list) or len(records) > 10000:
            raise ValueError()
        seen = set()
        for row in records:
            if any(not isinstance(row[key], str) or not row[key] for key in ("message_id", "current_id", "subject")):
                raise ValueError()
            if row["message_id"] in seen or not isinstance(row["actions"], list):
                raise ValueError()
            seen.add(row["message_id"])
            for index, step in enumerate(row["actions"]):
                if step["status"] not in ("pending", "uncertain", "done"):
                    raise ValueError()
                validate_rule({"name": step["rule"], "type": "match_default",
                               "modify": {step["action"]: step["settings"]}})
                if step["action"] == "Delete" and index != len(row["actions"]) - 1:
                    raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("Recovery record is invalid; preserve it for inspection.") from None
    return batch


def write_private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


class RunJournal:
    def __init__(self, mailbox_key, directory=None):
        from app.parser.parser import USER_OPTIONS_DIR
        digest = hashlib.sha256(mailbox_key.encode()).hexdigest()
        self.path = Path(directory or USER_OPTIONS_DIR / "runs") / f"{digest}.json"
        self.mailbox_key = mailbox_key

    @contextmanager
    def lock(self):
        # The supported desktop target is Linux; locks are released on crash.
        import fcntl
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.path.with_suffix(".lock").open("a") as stream:
            os.chmod(stream.name, 0o600)
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another window is processing this mailbox.") from None
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def load(self):
        if not self.path.exists():
            return None
        batch = validate_batch(json.loads(self.path.read_text(encoding="utf-8")))
        if batch.get("mailbox_key") != self.mailbox_key or batch.get("version") != 1:
            raise ValueError("Recovery record is invalid; preserve it for inspection.")
        return batch

    def save(self, batch):
        write_private_json(self.path, batch)

    def last_completed_id(self):
        report = self.path.with_name(self.path.stem + "-last-run.json")
        if report.exists():
            return json.loads(report.read_text(encoding="utf-8"))["batch_id"]
        return None

    def acknowledge(self, batch_id):
        with self.lock():
            self._acknowledge(batch_id)

    def _acknowledge(self, batch_id):
        batch = self.load()
        if batch and batch["batch_id"] == batch_id:
            if any(step["status"] != "done" for row in batch["records"] for step in row["actions"]):
                raise ValueError("Cannot clear an incomplete batch.")
            report = self.path.with_name(self.path.stem + "-last-run.json")
            write_private_json(report, batch)
            self.path.unlink()

    def commit(self, batch_id):
        from app.parser.parser import loadUserOptions, saveUserOptions
        with self.lock():
            batch = self.load()
            if batch is None and self.last_completed_id() == batch_id:
                return  # Another window has already committed this result.
            if batch is None or batch["batch_id"] != batch_id:
                raise ValueError("Mailbox recovery changed in another window; preview again.")
            if any(step["status"] != "done" for row in batch["records"] for step in row["actions"]):
                raise ValueError("Cannot commit an incomplete batch.")
            options = loadUserOptions()
            if options.get("mailbox_key") not in (None, self.mailbox_key):
                raise ValueError("The saved account changed in another window; sign in again.")
            options.update(batch["settings_update"])
            saveUserOptions(options)
            self._acknowledge(batch_id)

    def resolve(self, message_id, step_index, completed, batch_id=None):
        with self.lock():
            batch = self.load()
            if batch is None or (batch_id is not None and batch["batch_id"] != batch_id):
                raise ValueError("Recovery changed. Preview again.")
            row = next(row for row in batch["records"] if row["message_id"] == message_id)
            step = row["actions"][step_index]
            allowed = {"uncertain", "pending"} if completed else {"uncertain"}
            if step["status"] not in allowed:
                raise ValueError("This action no longer needs review.")
            step["status"] = "done" if completed else "pending"
            step["resolution"] = "verified-complete" if completed else "retry-approved"
            step.pop("error", None)
            self.save(batch)
