"""Provider contract used by the rule engine and sifting service."""
from abc import ABC, abstractmethod


class EmailAgent(ABC):
    mailbox_key = None

    @classmethod
    @abstractmethod
    def authenticate(cls):
        """Return a connected agent; called on the worker thread."""

    @abstractmethod
    def logout(self):
        """Remove saved authentication."""

    @abstractmethod
    async def get_emails(self, received_after=None, max_emails=100, *,
                         oldest_first=False, received_before=None,
                         checkpoint_ids=(), cancel=None):
        """Return inbox messages sorted by received_date_time, up to the limit.

        Messages expose id, subject, from_.email_address.address, body.content,
        and a UTC received_date_time. Oldest-first includes the lower timestamp
        boundary, excluding checkpoint IDs. The upper boundary is inclusive.
        """

    @abstractmethod
    async def delete(self, email):
        """Delete using the provider's normal delete operation."""

    @abstractmethod
    async def move(self, email, destination):
        """Move the message and update its ID if necessary."""

    @abstractmethod
    async def mark(self, email, kind, value):
        """Set Read/Unread or High/Normal/Low importance."""


def next_checkpoint(emails, previous_at, previous_ids, run_started_at):
    if not emails:
        return run_started_at, []
    boundary = emails[-1].received_date_time.isoformat().replace("+00:00", "Z")
    ids = set(previous_ids) if boundary == previous_at else set()
    ids.update(email.id for email in emails
               if email.received_date_time == emails[-1].received_date_time)
    return boundary, sorted(ids)
