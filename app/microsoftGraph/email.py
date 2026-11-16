from pathlib import Path
import os
from app.services.control import check_cancelled
from app.agents.base import next_checkpoint

from azure.identity import InteractiveBrowserCredential
from msgraph import GraphServiceClient
from msgraph.graph_request_adapter import GraphRequestAdapter, options as GRAPH_MIDDLEWARE_OPTIONS
from msgraph_core import GraphClientFactory
from kiota_authentication_azure.azure_identity_authentication_provider import AzureIdentityAuthenticationProvider
from kiota_http.middleware.options import RetryHandlerOption
from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)


SCOPES = ["Mail.ReadWrite"]
ENABLE_CAE = True
MAX_EMAILS = 100
AUTH_RECORD_FILE = Path.home() / ".email-sifting-auth.json"
REDIRECT_URI = "http://localhost:8400"

CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "4b454fd8-c82e-4595-b8c6-7a960fd2c4ae")
TENANT_ID = os.environ.get("MICROSOFT_TENANT_ID", "common")


def logout():
    AUTH_RECORD_FILE.unlink(missing_ok=True)


def authenticate():
    # Session-only tokens: no persistent refresh-token cache to leave behind.
    credential = InteractiveBrowserCredential(
        client_id=CLIENT_ID,
        tenant_id=TENANT_ID,
        redirect_uri=REDIRECT_URI,
        timeout=180,
        disable_automatic_authentication=True,
    )

    try:
        authentication_record = credential.authenticate(scopes=SCOPES, enable_cae=ENABLE_CAE)
    except Exception:
        credential.close()
        raise
    retry = RetryHandlerOption(max_retries=0)
    # Supplying a custom HTTP client bypasses GraphRequestAdapter's defaults.
    # Preserve its /users/me-token-to-replace -> /me rewrite and telemetry.
    middleware_options = {**GRAPH_MIDDLEWARE_OPTIONS, retry.get_key(): retry}
    http_client = GraphClientFactory.create_with_default_middleware(options=middleware_options)
    auth_provider = AzureIdentityAuthenticationProvider(credential, scopes=SCOPES, is_cae_enabled=ENABLE_CAE)
    adapter = GraphRequestAdapter(auth_provider, client=http_client)
    client = GraphServiceClient(request_adapter=adapter)
    client.email_sifting_credential = credential
    client.email_sifting_http_client = http_client
    client.email_sifting_mailbox_key = f"microsoft:{authentication_record.home_account_id}"
    return client


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
        top=min(max_emails, 1000),
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
        'outlook.body-content-type="text", IdType="ImmutableId"',
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
