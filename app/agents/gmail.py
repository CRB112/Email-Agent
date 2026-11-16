"""Personal Gmail adapter using Google's installed-application OAuth flow."""
import base64
import json
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

    @staticmethod
    def _client_config(credentials_file=None):
        path = Path(credentials_file or os.environ.get(
            "GMAIL_CLIENT_SECRET_FILE", "~/.config/EmailSiftingAgent/gmail-client.json"
        )).expanduser()
        try:
            with path.open(encoding="utf-8") as source:
                config = json.load(source)
        except OSError as error:
            raise ValueError(
                f"Cannot read Gmail client JSON at {path}. "
                "Use 'Choose Gmail client JSON...' to select the Desktop app "
                "OAuth client downloaded from Google Cloud."
            ) from error
        except (ValueError, UnicodeError) as error:
            raise ValueError(
                "Invalid Gmail client JSON. Download the Desktop app OAuth "
                "client JSON from Google Cloud and select it again."
            ) from error
        installed = config.get("installed") if isinstance(config, dict) else None
        if not isinstance(installed, dict) or "web" in config:
            raise ValueError(
                "Gmail requires a Desktop app OAuth client JSON with an "
                "'installed' section. Create a Desktop app client in Google "
                "Cloud, then download and select its JSON."
            )
        required = ("client_id", "client_secret", "auth_uri", "token_uri")
        missing = [key for key in required
                   if not isinstance(installed.get(key), str) or not installed[key].strip()]
        if missing:
            raise ValueError(
                f"Gmail client JSON is missing: {', '.join(missing)}. "
                "Download the complete Desktop app OAuth client JSON from "
                "Google Cloud and select it again."
            )
        return config

    @classmethod
    def authenticate(cls, credentials_file=None):
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        flow = InstalledAppFlow.from_client_config(cls._client_config(credentials_file), SCOPES)
        credentials = flow.run_local_server(port=0, timeout_seconds=180)
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
        if self.client is not None:
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
        # Gmail documents newest-first listing. Oldest-first needs every ID page,
        # but only the selected batch needs metadata and MIME bodies.
        ids = []
        excluded = set(checkpoint_ids)
        seen = set()
        selected = []
        page = None
        while True:
            check_cancelled(cancel)
            response = self._messages().list(
                userId="me", labelIds=["INBOX"], q=" ".join(query),
                maxResults=500, pageToken=page,
            ).execute()
            check_cancelled(cancel)
            candidates = [item["id"] for item in response.get("messages", [])]
            if oldest_first:
                ids.extend(candidates)
            else:
                selected.extend(self._select(candidates, max_emails - len(selected),
                                             lower, upper, excluded, seen, cancel, oldest_first))
                if len(selected) >= max_emails:
                    break
            page = response.get("nextPageToken")
            if not page:
                break
        if oldest_first:
            selected = self._select(reversed(ids), max_emails, lower, upper,
                                    excluded, seen, cancel, oldest_first)
        emails = []
        for message_id in selected:
            check_cancelled(cancel)
            record = self._messages().get(userId="me", id=message_id, format="raw").execute()
            check_cancelled(cancel)
            emails.append(self._email(record))
        emails.sort(key=lambda email: (email.received_date_time, email.id), reverse=not oldest_first)
        return emails

    def _select(self, candidates, limit, lower, upper, excluded, seen, cancel, inclusive):
        selected = []
        for message_id in candidates:
            check_cancelled(cancel)
            if message_id in seen or message_id in excluded:
                continue
            seen.add(message_id)
            metadata = self._messages().get(userId="me", id=message_id, format="minimal",
                                            fields="id,internalDate").execute()
            check_cancelled(cancel)
            date = datetime.fromtimestamp(int(metadata["internalDate"]) / 1000, timezone.utc)
            if lower and (date < lower or (date == lower and not inclusive)):
                continue
            if upper and date > upper:
                continue
            selected.append(message_id)
            if len(selected) >= limit:
                break
        return selected

    async def list_destinations(self):
        labels = self.client.users().labels().list(userId="me").execute().get("labels", [])
        self._labels = labels
        return {"Archive": "archive", **{label["name"]: label["id"] for label in labels
                                          if label.get("type") == "user"}}

    async def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    async def delete(self, email):
        return self._messages().trash(userId="me", id=email.id).execute()

    async def move(self, email, destination):
        if destination.lower() == "archive":
            added = []
        else:
            labels = getattr(self, "_labels", None)
            if labels is None:
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
