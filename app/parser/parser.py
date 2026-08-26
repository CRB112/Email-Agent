import json
import asyncio
from pathlib import Path
from parser.MatchCommands import COMMAND_CLASSES
from parser.ModifyCommands import MODIFY_CLASSES, Delete
from microsoftGraph.email import graph_client

OPTIONS_FILE = Path(__file__).parent.parent / "user" / "useroptions.json"

def loadUserOptions() -> dict:
    with OPTIONS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

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

        modify_list = [
            MODIFY_CLASSES[modify_type](settings)
            for modify_type, settings in rule.get("modify", {}).items()
        ]
        rulesObj.append((rule_object, modify_list))

    return rulesObj

async def parseEmailsWithJson(emails):
    rules = parseUserOptions()

    for email in emails:
        deleted = False
        for rule, modify in rules:
            if rule.testMatch(email):
                for m in modify:
                    await m.modify(email, graph_client)
                    if isinstance(m, Delete):
                        deleted = True
                        break

            if deleted:
                break