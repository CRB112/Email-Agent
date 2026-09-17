"""Personal Gmail adapter using Google's installed-application OAuth flow."""
import base64
import os
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path
from types import SimpleNamespace

from app.agents.base import EmailAgent
from app.services.control import check_cancelled

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailAgent(EmailAgent):
    def __init__(self, client):
        self.client = client

    @classmethod
    def authenticate(cls, credentials_file=None):
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        path = Path(credentials_file or os.environ.get(
            "GMAIL_CLIENT_SECRET_FILE", "~/.config/EmailSiftingAgent/gmail-client.json"
        )).expanduser()
        flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
        credentials = flow.run_local_server(port=0)
        client = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        try:
            profile = client.users().getProfile(userId="me").execute()
        except Exception:
            client.close()
            raise
        agent = cls(client)
        agent.mailbox_key = f"gmail:{profile['emailAddress'].lower()}"
        return agent

    def logout(self):
        # Credentials are session-only and never written to disk.
        self.client.close()
        self.client = None

    def _messages(self):
        return self.client.users().messages()

    @staticmethod
    def _email(record):
        raw = record["raw"]
        message = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        body = message.get_body(preferencelist=("plain", "html"))
        content = body.get_content() if body else ""
        if not isinstance(content, str):
            content = ""
        return SimpleNamespace(
            id=record["id"], subject=str(message.get("Subject", "")),
            from_=SimpleNamespace(email_address=SimpleNamespace(
                address=parseaddr(str(message.get("From", "")))[1])),
            body=SimpleNamespace(content=content),
            received_date_time=datetime.fromtimestamp(
                int(record["internalDate"]) / 1000, timezone.utc),
        )

    async def get_emails(self, received_after=None, max_emails=100, *,
                         oldest_first=False, received_before=None,
                         checkpoint_ids=(), cancel=None):
        if max_emails < 1:
            raise ValueError("max_emails must be positive")
        lower = datetime.fromisoformat(received_after.replace("Z", "+00:00")) if received_after else None
        upper = datetime.fromisoformat(received_before.replace("Z", "+00:00")) if received_before else None
        query = []
        # Gmail search has second precision; exact inclusive boundaries are
        # enforced locally against internalDate after fetching each message.
        if lower:
            query.append(f"after:{int(lower.timestamp()) - 1}")
        if upper:
            query.append(f"before:{int(upper.timestamp()) + 1}")
        emails = []
        seen = set(checkpoint_ids)
        page = None
        while True:
            check_cancelled(cancel)
            response = self._messages().list(
                userId="me", labelIds=["INBOX"], q=" ".join(query),
                maxResults=500, pageToken=page,
            ).execute()
            check_cancelled(cancel)
            for item in response.get("messages", []):
                check_cancelled(cancel)
                if item["id"] in seen:
                    continue
                record = self._messages().get(userId="me", id=item["id"], format="raw").execute()
                check_cancelled(cancel)
                email = self._email(record)
                seen.add(email.id)
                date = email.received_date_time
                if lower and (date < lower or (date == lower and not oldest_first)):
                    continue
                if upper and date > upper:
                    continue
                emails.append(email)
            page = response.get("nextPageToken")
            if not page:
                break
        # Gmail does not offer an oldest-first list order. Read all candidate
        # pages before limiting, otherwise a backlog can be skipped forever.
        emails.sort(key=lambda email: (email.received_date_time, email.id),
                    reverse=not oldest_first)
        return emails[:max_emails]

    async def delete(self, email):
        return self._messages().trash(userId="me", id=email.id).execute()

    async def move(self, email, destination):
        if destination.lower() == "archive":
            added = []
        else:
            labels = self.client.users().labels().list(userId="me").execute().get("labels", [])
            label = next((label for label in labels
                          if label["id"] == destination or label["name"] == destination), None)
            if label is None:
                raise ValueError(f"Gmail label does not exist: {destination}")
            if label["id"] == "INBOX":
                return self._modify(email, ["INBOX"], [])
            if label.get("type") == "system":
                raise ValueError("Choose a Gmail user label or archive")
            added = [label["id"]]
        return self._modify(email, added, ["INBOX"])

    def _modify(self, email, added, removed):
        return self._messages().modify(userId="me", id=email.id, body={
            "addLabelIds": added, "removeLabelIds": removed,
        }).execute()

    async def mark(self, email, kind, value):
        value = value.lower()
        if kind == "Read" and value in {"read", "unread"}:
            return self._modify(email, ["UNREAD"] if value == "unread" else [],
                                ["UNREAD"] if value == "read" else [])
        if kind == "Importance" and value in {"high", "normal", "low"}:
            return self._modify(email, ["IMPORTANT"] if value == "high" else [],
                                [] if value == "high" else ["IMPORTANT"])
        raise ValueError(f"Unsupported mark: {kind} {value}")
