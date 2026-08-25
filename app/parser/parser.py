import json
from pathlib import Path
from parser.commands import COMMAND_CLASSES

OPTIONS_FILE = Path(__file__).parent.parent / "user" / "useroptions.json"

def loadUserOptions() -> dict:
    with OPTIONS_FILE.open('r', encoding="utf-8") as f:
        return json.load(f)

def parseUserOptions():
    options = loadUserOptions()
    rules = sorted(options.get("rules", []), key=lambda rule: rule.get("priority", 100))
    rulesObj = []
    for rule in rules:
        rulesObj.append(COMMAND_CLASSES.get(rule.get("type"))(rule.get("settings")))
    return rulesObj

def parseEmailsWithJson(emails):
    rules = parseUserOptions()
    for email in emails:
        for rule in rules:
            if rule.testMatch(email):
                print("zaza")
            else:
                print("pookums")
