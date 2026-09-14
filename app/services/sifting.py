from dataclasses import dataclass
from datetime import datetime, timezone

from app.microsoftGraph.email import getEmails, next_checkpoint
from app.parser.parser import parseEmailsWithJson
from app.services.control import check_cancelled


@dataclass
class SiftResult:
    examined: int
    modified: int
    modifications: int
    settings_update: dict


async def sift(graph_client, options, mode, cancel, report):
    """Process a settings snapshot; return checkpoint changes only on success."""
    check_cancelled(cancel)
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
        updates["last_sift_at"], updates["last_sift_ids"] = next_checkpoint(
            emails, previous, ids, started,
        )
    report("Sifting emails...", 0, len(emails))
    modified, modifications = await parseEmailsWithJson(
        emails, graph_client, options=options, cancel=cancel,
        progress=lambda done, total: report("Sifting emails...", done, total),
    )
    return SiftResult(len(emails), modified, modifications, updates)
