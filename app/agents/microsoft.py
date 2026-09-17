"""Microsoft Graph SDK adapter."""
from msgraph.generated.models.message import Message
from msgraph.generated.models.importance import Importance
from msgraph.generated.users.item.messages.item.move.move_post_request_body import MovePostRequestBody
from app.agents.base import EmailAgent
from app.microsoftGraph import email as graph


class MicrosoftGraphAgent(EmailAgent):
    def __init__(self, client):
        self.client = client

    @classmethod
    def authenticate(cls):
        agent = cls(graph.authenticate())
        record = graph.AuthenticationRecord.deserialize(
            graph.AUTH_RECORD_FILE.read_text(encoding="utf-8"))
        agent.mailbox_key = f"microsoft:{record.home_account_id}"
        return agent

    def logout(self):
        graph.logout()

    async def get_emails(self, received_after=None, max_emails=100, **kwargs):
        if max_emails < 1:
            raise ValueError("max_emails must be positive")
        return await graph.getEmails(self.client, received_after, max_emails, **kwargs)

    async def delete(self, email):
        return await self.client.me.messages.by_message_id(email.id).delete()

    async def move(self, email, destination):
        result = await self.client.me.messages.by_message_id(email.id).move.post(
            MovePostRequestBody(destination_id=destination))
        if result and result.id:
            email.id = result.id
        return result

    async def mark(self, email, kind, value):
        request = Message()
        if kind == "Read":
            request.is_read = value.lower() == "read"
        elif kind == "Importance":
            request.importance = Importance(value.lower())
        else:
            raise ValueError(f"Unknown mark type: {kind}")
        return await self.client.me.messages.by_message_id(email.id).patch(request)
