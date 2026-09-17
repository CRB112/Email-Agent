from pathlib import Path
from app.services.control import check_cancelled
from app.agents.base import next_checkpoint

from azure.identity import (
    AuthenticationRecord,
    InteractiveBrowserCredential,
    TokenCachePersistenceOptions,
)
from msgraph import GraphServiceClient
from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)


SCOPES = ["Mail.ReadWrite"]
MAX_EMAILS = 100
AUTH_RECORD_FILE = Path.home() / ".email-sifting-auth.json"
REDIRECT_URI = "http://localhost:8400"

CLIENT_ID = "4b454fd8-c82e-4595-b8c6-7a960fd2c4ae"
TENANT_ID = "common"


def logout():
    AUTH_RECORD_FILE.unlink(missing_ok=True)


def authenticate():
    cache_options = TokenCachePersistenceOptions(
        name="EmailSiftingAgent",
        allow_unencrypted_storage=True,
    )

    authentication_record = None

    if AUTH_RECORD_FILE.exists():
        authentication_record = AuthenticationRecord.deserialize(
            AUTH_RECORD_FILE.read_text(encoding="utf-8")
        )

    credential = InteractiveBrowserCredential(
        client_id=CLIENT_ID,
        tenant_id=TENANT_ID,
        redirect_uri=REDIRECT_URI,
        cache_persistence_options=cache_options,
        authentication_record=authentication_record,
    )

    # Only start interactive login if there is no saved record.
    if authentication_record is None:
        authentication_record = credential.authenticate(scopes=SCOPES)

        AUTH_RECORD_FILE.write_text(
            authentication_record.serialize(),
            encoding="utf-8",
        )

    return GraphServiceClient(
        credentials=credential,
        scopes=SCOPES,
    )


async def getEmails(
    graph_client, received_after=None, max_emails=MAX_EMAILS, *,
    oldest_first=False, received_before=None, checkpoint_ids=(), cancel=None,
):
    filters = []
    if received_after:
        operator = "ge" if oldest_first else "gt"
        filters.append(f"receivedDateTime {operator} {received_after}")
    if received_before:
        filters.append(f"receivedDateTime le {received_before}")

    query = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=max_emails,
        orderby=["receivedDateTime asc" if oldest_first else "receivedDateTime desc"],
        filter=" and ".join(filters) or None,
    )
    request_configuration = (
        MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query
        )
    )
    request_configuration.headers.add(
        "Prefer",
        'outlook.body-content-type="text"',
    )

    builder = graph_client.me.mail_folders.by_mail_folder_id(
        "inbox"
    ).messages
    emails = []
    seen_ids = set(checkpoint_ids)
    while True:
        check_cancelled(cancel)
        messages = await builder.get(request_configuration=request_configuration)
        check_cancelled(cancel)
        for email in messages.value or []:
            if email.id in seen_ids:
                continue
            emails.append(email)
            seen_ids.add(email.id)
            if len(emails) >= max_emails:
                return emails
        if not messages.odata_next_link:
            return emails
        builder = builder.with_url(messages.odata_next_link)
