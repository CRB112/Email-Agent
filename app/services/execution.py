"""Freeze matches before execution and retain per-action outcomes."""
import copy
from types import SimpleNamespace

from app.parser.MatchCommands import Match_default
from app.parser.ModifyCommands import MODIFY_CLASSES, Delete
from app.services.control import check_cancelled, SiftCancelled


class ProcessingFailure(RuntimeError):
    def __init__(self, message, records):
        super().__init__(message)
        self.records = records


def plan_actions(emails, options):
    from app.parser.parser import parseUserOptions
    rules = parseUserOptions(options)
    names = [rule["name"] for rule in sorted(options.get("rules", []), key=lambda rule: rule.get("priority", 100))]
    normal, fallback = [], []
    for name, (matcher, actions) in zip(names, rules):
        (fallback if isinstance(matcher, Match_default) else normal).append((name, matcher, actions))
    records = []
    for email in emails:
        matches = [(name, actions) for name, matcher, actions in normal if matcher.testMatch(email)]
        if not matches:
            matches = [(name, actions) for name, _, actions in fallback]
        steps = []
        deleted = False
        for name, actions in matches:
            for action in actions:
                steps.append({"rule": name, "action": type(action).__name__,
                              "settings": copy.deepcopy(action.settings), "status": "pending"})
                if isinstance(action, Delete):
                    deleted = True
                    break
            if deleted:
                break
        records.append({"message_id": email.id, "current_id": email.id,
                        "subject": email.subject or "(no subject)", "actions": steps})
    return records


async def execute_plan(records, agent, *, cancel=None, progress=None, persist=None):
    if any(step["status"] == "uncertain" for row in records for step in row["actions"]):
        raise ProcessingFailure("Review uncertain actions before resuming this batch.", records)
    for index, row in enumerate(records):
        try:
            check_cancelled(cancel)
        except SiftCancelled as error:
            error.records = records
            raise
        email = SimpleNamespace(id=row["current_id"])
        for step in row["actions"]:
            if step["status"] == "done":
                continue
            step["status"] = "uncertain"
            if persist:
                persist()
            try:
                await MODIFY_CLASSES[step["action"]](step["settings"]).modify(email, agent)
                row["current_id"] = email.id
                step["status"] = "done"
                step.pop("error", None)
                if persist:
                    persist()
            except Exception as error:
                step["status"] = "uncertain"
                step["error"] = str(error)
                if persist:
                    persist()
                raise ProcessingFailure(str(error), records) from error
        if progress:
            progress(index + 1, len(records))
    modified = sum(any(step["status"] == "done" for step in row["actions"]) for row in records)
    modifications = sum(step["status"] == "done" for row in records for step in row["actions"])
    return modified, modifications
