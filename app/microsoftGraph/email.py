from pathlib import Path

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


def authenticate():
    """Authenticate the user and return a Microsoft Graph client."""

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


async def getEmails(graph_client):
    """Return the newest messages from the signed-in user's inbox."""

    query = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=MAX_EMAILS,
        orderby=["receivedDateTime desc"],
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

    messages = await graph_client.me.mail_folders.by_mail_folder_id(
        "inbox"
    ).messages.get(request_configuration=request_configuration)
    return messages.value or []
