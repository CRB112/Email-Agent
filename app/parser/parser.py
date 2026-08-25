import json
from pathlib import Path

OPTIONS_FILE = Path(__file__).parent.parent / "user" / "useroptions.json"

def loadUserOptions() -> dict:
    with OPTIONS_FILE.open('r', encoding="utf-8") as f:
        return json.load(f)


def getSenderAddress(email) -> str:
    if email.from_ and email.from_.email_address:
        return (email.from_.email_address.address or "").lower()
    return ""


def matchesSenderAddress(sender, match) -> bool:
    addresses = [address.lower() for address in match.get("sender_addresses", [])]
    return not addresses or sender in addresses


def matchesSenderDomain(sender, match) -> bool:
    domains = [domain.lower().lstrip("@") for domain in match.get("sender_domains", [])]
    if not domains:
        return True

    sender_domain = sender.rsplit("@", 1)[-1] if "@" in sender else ""
    return sender_domain in domains


def matchesSubject(subject, match) -> bool:
    terms = [term.lower() for term in match.get("subject_contains_any", [])]
    return not terms or any(term in subject for term in terms)


def emailMatchesRule(email, rule) -> bool:
    match = rule.get("match", {})
    sender = getSenderAddress(email)
    subject = (email.subject or "").lower()

    return (
        matchesSenderAddress(sender, match)
        and matchesSenderDomain(sender, match)
        and matchesSubject(subject, match)
    )


def parseEmailsWithJson(emails):
    options = loadUserOptions()
    rules = sorted(options.get("rules", []), key=lambda rule: rule.get("priority", 100))

    for email in emails:
        for rule in rules:
            if not rule.get("enabled", True):
                continue

            if emailMatchesRule(email, rule):
                print(rule["name"], email.subject)
                break
