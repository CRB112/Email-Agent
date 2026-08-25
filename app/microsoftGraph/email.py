import asyncio

from msgraph import GraphServiceClient
from azure.identity import (DeviceCodeCredential, TokenCachePersistenceOptions)

cache_options = TokenCachePersistenceOptions(
    name="EmailSiftingAgent",
    allow_unencrypted_storage=True
)

credential = DeviceCodeCredential(
    client_id="4b454fd8-c82e-4595-b8c6-7a960fd2c4ae",
    tenant_id="common",
    cache_persistence_options=cache_options
)

graph_client = GraphServiceClient(
    credentials=credential,
    scopes=['Mail.ReadWrite']
)

async def getEmails():
    messages = await graph_client.me.messages.get()
    return messages.value
