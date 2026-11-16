import json
import sys
import os
from pathlib import Path
from app.parser.MatchCommands import COMMAND_CLASSES, Match_default
from app.parser.ModifyCommands import MODIFY_CLASSES
from app.rules.validation import validate_options

APP_NAME = "EmailSiftingAgent"
USER_OPTIONS_DIR = Path(os.environ.get("EMAIL_SIFTING_DATA_DIR", Path.home() / ".config" / APP_NAME)).expanduser()
OPTIONS_FILE = USER_OPTIONS_DIR / "useroptions.json"

if getattr(sys, "frozen", False):
    DEFAULT_OPTIONS_FILE = (
        Path(sys._MEIPASS) / "app" / "user" / "useroptions.json"
    )
else:
    DEFAULT_OPTIONS_FILE = (
        Path(__file__).resolve().parent.parent / "user" / "useroptions.json"
    )


def ensureUserOptions() -> None:
    """Create the persistent user options file from the bundled default."""

    USER_OPTIONS_DIR.mkdir(parents=True, exist_ok=True)

    if not OPTIONS_FILE.exists():
        from app.services.journal import write_private_json
        defaults = json.loads(DEFAULT_OPTIONS_FILE.read_text(encoding="utf-8"))
        write_private_json(OPTIONS_FILE, validate_options(defaults))

def loadUserOptions() -> dict:
    ensureUserOptions()

    with OPTIONS_FILE.open("r", encoding="utf-8") as f:
        return validate_options(json.load(f))


def saveUserOptions(options: dict) -> None:
    validate_options(options)
    ensureUserOptions()
    from app.services.journal import write_private_json
    write_private_json(OPTIONS_FILE, options)

def parseUserOptions(options=None):
    if options is None:
        options = loadUserOptions()
    validate_options(options)
    rules = sorted(
        options.get("rules", []),
        key=lambda rule: rule.get("priority", 100)
    )
    rulesObj = []

    for rule in rules:
        rule_class = COMMAND_CLASSES[rule["type"]]
        rule_object = rule_class(rule.get("settings", {}))

        # Mark the current message before Move can relocate it, and perform
        # destructive deletion only after every other action.
        action_order = {"Mark": 0, "Move": 1, "Delete": 2}
        modify_items = sorted(
            rule.get("modify", {}).items(),
            key=lambda item: action_order.get(item[0], 0),
        )
        modify_list = [
            MODIFY_CLASSES[modify_type](settings)
            for modify_type, settings in modify_items
        ]
        rulesObj.append((rule_object, modify_list))

    return rulesObj

async def parseEmailsWithJson(emails, graph_client, *, options=None, cancel=None, progress=None):
    from app.services.execution import plan_actions, execute_plan
    if options is None:
        options = loadUserOptions()
    records = plan_actions(emails, options)
    return await execute_plan(records, graph_client, cancel=cancel, progress=progress)
