"""Editable defaults for every matcher and action supported by the parser."""

import copy


MATCH_DEFINITIONS = {
    "match_subject": {"Sub": ""},
    "match_sender": {"Sender": ""},
    "match_domain": {"Domain": ""},
    "match_body_contains": {
        "Words": [],
        "Type": "Any",
        "CaseSensitive": False,
    },
    "match_subject_contains": {
        "Words": [],
        "Type": "Any",
        "CaseSensitive": False,
    },
    "match_sender_contains": {
        "Words": [],
        "Type": "Any",
        "CaseSensitive": False,
    },
}


def match_type_label(match_type):
    """Convert an internal matcher name into a user-facing label."""
    if match_type == "match_body":
        match_type = "match_body_contains"
    return match_type.removeprefix("match_").replace("_", " ").title()


MATCH_TYPES_BY_LABEL = {
    match_type_label(match_type): match_type
    for match_type in MATCH_DEFINITIONS
}


ACTION_DEFINITIONS = {
    "Delete": {},
    "Move": {"Folder": ""},
    "Mark": {"Mark_type": "Read"},
}


def create_rule_template():
    """Return a fresh, valid rule for the new-rule editor."""
    match_type = "match_subject_contains"
    action_type = "Mark"
    return {
        "name": "New rule",
        "type": match_type,
        "settings": copy.deepcopy(MATCH_DEFINITIONS[match_type]),
        "modify": {
            action_type: copy.deepcopy(ACTION_DEFINITIONS[action_type]),
        },
        "priority": 100,
    }
