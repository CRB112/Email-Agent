"""Run real rule processing against local JSON emails and a recording fake."""

import argparse
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from app.parser.parser import parseEmailsWithJson
from tests.fakes import FakeGraph, make_email


ROOT = Path(__file__).resolve().parent.parent


async def simulate(options, records):
    emails = [make_email(**record) for record in records]
    ids = [email.id for email in emails]
    if len(ids) != len(set(ids)):
        raise ValueError("Each fake email must have a unique id.")
    graph = FakeGraph()
    with patch("app.parser.parser.loadUserOptions", return_value=options):
        modified, modifications = await parseEmailsWithJson(emails, graph)
    return {
        "emails_supplied": len(emails),
        "emails_modified": modified,
        "modifications": modifications,
        "actions": graph.actions,
        "unchanged_email_ids": [email.id for email in emails
                                if email.id not in {action["email_id"] for action in graph.actions}],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, default=ROOT / "app/user/useroptions.json",
                        help="Options JSON containing a rules array (read only).")
    parser.add_argument("--emails", type=Path, default=ROOT / "tests/fixtures/inbox.json",
                        help="JSON array of fake email records (read only).")
    args = parser.parse_args()
    try:
        options = json.loads(args.rules.read_text(encoding="utf-8"))
        records = json.loads(args.emails.read_text(encoding="utf-8"))
        result = asyncio.run(simulate(options, records))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Simulation failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
