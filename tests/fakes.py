"""Small Graph substitute: records actions and never creates a network client."""

from datetime import datetime, timezone
from types import SimpleNamespace


def make_email(id="email-1", subject="Hello", sender="person@example.com", body="",
               received_at=None):
    return SimpleNamespace(
        id=id,
        subject=subject,
        from_=SimpleNamespace(email_address=SimpleNamespace(address=sender)),
        body=SimpleNamespace(content=body),
        received_date_time=(datetime.fromisoformat(received_at.replace("Z", "+00:00"))
                            if received_at else datetime(2026, 1, 1, tzinfo=timezone.utc)),
    )


class FakeGraph:
    def __init__(self, fail_on=None):
        self.actions = []
        self.fail_on = fail_on
        self.me = self
        self.messages = self

    def by_message_id(self, message_id):
        return FakeMessage(self, message_id)

    def record(self, message_id, action, **settings):
        if action == self.fail_on:
            raise RuntimeError(f"Simulated {action} failure")
        self.actions.append({"email_id": message_id, "action": action, **settings})


class FakeMessage:
    def __init__(self, graph, message_id):
        self.graph = graph
        self.message_id = message_id
        self.move = self

    async def delete(self):
        self.graph.record(self.message_id, "Delete")

    async def patch(self, request_body):
        settings = {}
        if request_body.is_read is not None:
            settings["is_read"] = request_body.is_read
        if request_body.importance is not None:
            settings["importance"] = request_body.importance.value
        self.graph.record(self.message_id, "Mark", **settings)

    async def post(self, request_body):
        self.graph.record(self.message_id, "Move", folder=request_body.destination_id)
        return SimpleNamespace(id=f"moved-{self.message_id}")


def make_rule(match_type="match_subject_contains", settings=None, actions=None, priority=100):
    return {
        "name": "Test rule",
        "type": match_type,
        "settings": {"Words": ["invoice"], "Type": "Any"} if settings is None else settings,
        "modify": {"Mark": {"Mark_type": "Read"}} if actions is None else actions,
        "priority": priority,
    }
