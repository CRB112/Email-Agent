"""Validation shared by settings, the editor, and the execution boundary."""
from datetime import datetime

from app.rules.definitions import MATCH_DEFINITIONS, ACTION_DEFINITIONS


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty.")


def validate_rule(rule):
    if not isinstance(rule, dict):
        raise ValueError("Each rule must be an object.")
    _text(rule.get("name"), "Rule name")
    prefix = f"Rule '{rule['name']}'"
    kind = rule.get("type")
    if kind == "match_body":
        kind = "match_body_contains"
    if not isinstance(kind, str) or kind not in MATCH_DEFINITIONS:
        raise ValueError(f"{prefix}: unknown match type.")
    if type(rule.get("priority", 100)) is not int:
        raise ValueError(f"{prefix}: priority must be a whole number.")
    settings = rule.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError(f"{prefix}: conditions must be an object.")
    if kind.endswith("_contains"):
        words = settings.get("Words")
        if not isinstance(words, list) or not words:
            raise ValueError(f"{prefix}: enter at least one keyword; use Default for unmatched mail.")
        for word in words:
            _text(word, f"{prefix}: keyword")
        if settings.get("Type", "All") not in ("Any", "All"):
            raise ValueError(f"{prefix}: keyword mode must be Any or All.")
        if type(settings.get("CaseSensitive", False)) is not bool:
            raise ValueError(f"{prefix}: CaseSensitive must be true or false.")
    elif kind != "match_default":
        field = {"match_subject": "Sub", "match_sender": "Sender", "match_domain": "Domain"}[kind]
        _text(settings.get(field), f"{prefix}: {field}")
    actions = rule.get("modify")
    if not isinstance(actions, dict) or not actions:
        raise ValueError(f"{prefix}: add at least one action.")
    for action, values in actions.items():
        if action not in ACTION_DEFINITIONS or not isinstance(values, dict):
            raise ValueError(f"{prefix}: invalid action {action!r}.")
        if action == "Move":
            _text(values.get("Folder"), f"{prefix}: destination")
        if action == "Mark":
            kind = values.get("Mark_type")
            choices = {"Read": ("Read", "Unread"), "Importance": ("Low", "Normal", "High")}
            default = "Read" if kind == "Read" else "Normal"
            if not isinstance(kind, str) or kind not in choices or values.get("Mark_op", default) not in choices[kind]:
                raise ValueError(f"{prefix}: invalid Mark operation.")


def validate_options(options):
    if not isinstance(options, dict):
        raise ValueError("Settings must be a JSON object.")
    if type(options.get("schema_version", 1)) is not int or options.get("schema_version", 1) != 1:
        raise ValueError("Unsupported settings version.")
    limit = options.get("max_emails", 100)
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("Maximum emails must be between 1 and 10000.")
    if options.get("sift_mode", "since_last") not in ("since_last", "all"):
        raise ValueError("Unknown sift mode.")
    rules = options.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("Rules must be an array.")
    for rule in rules:
        validate_rule(rule)
    if options.get("last_sift_at") is not None:
        try:
            date = datetime.fromisoformat(options["last_sift_at"].replace("Z", "+00:00"))
            if date.utcoffset() is None:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Checkpoint must be a timestamp with a timezone.") from None
    ids = options.get("last_sift_ids", [])
    if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
        raise ValueError("Checkpoint IDs must be an array of strings.")
    return options
