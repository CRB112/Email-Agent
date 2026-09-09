import json
import shutil
import sys
from pathlib import Path
from app.parser.MatchCommands import COMMAND_CLASSES, Match_default
from app.parser.ModifyCommands import MODIFY_CLASSES, Delete

APP_NAME = "EmailSiftingAgent"
USER_OPTIONS_DIR = Path.home() / ".config" / APP_NAME
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
        shutil.copyfile(DEFAULT_OPTIONS_FILE, OPTIONS_FILE)

def loadUserOptions() -> dict:
    ensureUserOptions()

    with OPTIONS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def saveUserOptions(options: dict) -> None:
    ensureUserOptions()
    temporary_file = OPTIONS_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(options, file, indent=2)
        file.write("\n")

    temporary_file.replace(OPTIONS_FILE)

def parseUserOptions():
    options = loadUserOptions()
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

async def parseEmailsWithJson(emails, graph_client):
    rules = parseUserOptions()
    normal_rules = [
        rule_data for rule_data in rules
        if not isinstance(rule_data[0], Match_default)
    ]
    default_rules = [
        rule_data for rule_data in rules
        if isinstance(rule_data[0], Match_default)
    ]
    num_emails = 0
    num_modifications = 0

    for email in emails:
        deleted = False
        matched_normal_rule = False
        email_was_modified = False

        for rule, modify in normal_rules:
            if rule.testMatch(email):
                matched_normal_rule = True
                for m in modify:
                    await m.modify(email, graph_client)
                    num_modifications += 1
                    email_was_modified = True
                    if isinstance(m, Delete):
                        deleted = True
                        break

            if deleted:
                break

        if not matched_normal_rule and not deleted:
            for _, modify in default_rules:
                for m in modify:
                    await m.modify(email, graph_client)
                    num_modifications += 1
                    email_was_modified = True
                    if isinstance(m, Delete):
                        deleted = True
                        break

                if deleted:
                    break

        if email_was_modified:
            num_emails += 1

    return num_emails, num_modifications
