from msgraph import GraphServiceClient
from azure.identity import (DeviceCodeCredential, TokenCachePersistenceOptions)

cache_options = TokenCachePersistenceOptions(
    name="Mail App"
)

credential = DeviceCodeCredential(
    client_id="Client_ID",
    tenant_id="common",
    cache_persistence_options=cache_options
)

graph_client = GraphServiceClient(
    credentials=credential,
    scopes=['Mail.Read']
)

