import copy
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.agents import as_agent, getEmails
from app.agents.base import next_checkpoint
from app.rules.validation import validate_options
from app.services.control import check_cancelled
from app.services.execution import plan_actions, execute_plan
from app.services.journal import RunJournal, validate_batch


@dataclass
class SiftResult:
    examined: int
    modified: int
    modifications: int
    settings_update: dict
    records: list = field(default_factory=list)
    preview: bool = False
    batch: dict | None = None
    journal: object = None
    warnings: list = field(default_factory=list)


async def sift(graph_client, options, mode, cancel, report, *, preview=False, prepared=None, journal=None):
    """Preview a frozen batch or execute it, retaining progress until committed."""
    check_cancelled(cancel)
    validate_options(options)
    if mode not in {"since_last", "all"}:
        raise ValueError("Unknown sift mode")
    agent = as_agent(graph_client)
    mailbox_key = agent.mailbox_key
    journal = journal or (RunJournal(mailbox_key) if mailbox_key else None)
    with journal.lock() if journal else nullcontext():
        batch = journal.load() if journal else None
        if batch and prepared is not None and batch["batch_id"] != prepared["batch_id"]:
            raise ValueError("Recovery changed in another window. Preview again.")
        if batch is None and prepared is not None:
            if journal and prepared.get("previous_batch_id") != journal.last_completed_id():
                raise ValueError("This preview is stale or already applied. Preview again.")
            batch = copy.deepcopy(prepared)
            if batch["mailbox_key"] != mailbox_key:
                raise ValueError("Preview belongs to a different mailbox. Preview again.")
        if batch is None:
            started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            previous = options.get("last_sift_at") if mode == "since_last" else None
            ids = options.get("last_sift_ids", []) if mode == "since_last" else []
            report("Refreshing inbox...", 0, 0)
            emails = await getEmails(
                graph_client, previous, options.get("max_emails", 100),
                oldest_first=mode == "since_last", received_before=started,
                checkpoint_ids=ids, cancel=cancel,
            )
            check_cancelled(cancel)
            updates = {"sift_mode": mode}
            if mode == "since_last":
                updates["last_sift_at"], updates["last_sift_ids"] = next_checkpoint(emails, previous, ids, started)
            batch = {"version": 1, "batch_id": uuid4().hex, "mailbox_key": mailbox_key,
                     "previous_batch_id": journal.last_completed_id() if journal else None,
                     "settings_update": updates, "records": plan_actions(emails, options)}
        validate_batch(batch)
        records = batch["records"]
        destinations = {step["settings"]["Folder"] for row in records for step in row["actions"]
                        if step["action"] == "Move" and step["status"] == "pending"}
        warnings = []
        if destinations:
            try:
                await agent.validate_destinations(destinations)
            except Exception as error:
                if not preview:
                    from app.services.execution import ProcessingFailure
                    raise ProcessingFailure(f"Destination check failed: {error}", records) from error
                warnings.append(f"Destination check failed: {error}")
        check_cancelled(cancel)
        if preview:
            return SiftResult(len(records), 0, 0, {}, records, True, copy.deepcopy(batch), journal, warnings)
        if journal:
            journal.save(batch)
        report("Applying rules...", 0, len(records))
        modified, modifications = await execute_plan(
            records, agent, cancel=cancel,
            progress=lambda done, total: report("Applying rules...", done, total),
            persist=(lambda: journal.save(batch)) if journal else None,
        )
        return SiftResult(len(records), modified, modifications, batch["settings_update"],
                          records, False, batch, journal)
