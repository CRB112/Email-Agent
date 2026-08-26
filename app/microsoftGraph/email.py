from pathlib import Path

from azure.identity import (
    AuthenticationRecord,
    DeviceCodeCredential,
    TokenCachePersistenceOptions,
)
from msgraph import GraphServiceClient
from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)

SCOPES = ["Mail.ReadWrite"]
MAX_EMAILS = 100
AUTH_RECORD_FILE = Path.home() / ".email-sifting-auth.json"

cache_options = TokenCachePersistenceOptions(
    name="EmailSiftingAgent",
    allow_unencrypted_storage=True,
)

authentication_record = None

if AUTH_RECORD_FILE.exists():
    authentication_record = AuthenticationRecord.deserialize(
        AUTH_RECORD_FILE.read_text(encoding="utf-8")
    )

credential = DeviceCodeCredential(
    client_id="4b454fd8-c82e-4595-b8c6-7a960fd2c4ae",
    tenant_id="common",
    cache_persistence_options=cache_options,
    authentication_record=authentication_record,
)

if authentication_record is None:
    authentication_record = credential.authenticate(scopes=SCOPES)
    AUTH_RECORD_FILE.write_text(
        authentication_record.serialize(),
        encoding="utf-8",
    )

graph_client = GraphServiceClient(
    credentials=credential,
    scopes=SCOPES,
)


async def getEmails():
    query = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=MAX_EMAILS,
        orderby=["receivedDateTime desc"],
    )
    request_configuration = (
        MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query
        )
    )
    messages = await graph_client.me.mail_folders.by_mail_folder_id(
        "inbox"
    ).messages.get(request_configuration=request_configuration)
    return messages.value
