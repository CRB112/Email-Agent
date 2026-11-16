"""Microsoft Graph SDK adapter."""
from msgraph.generated.models.message import Message
from msgraph.generated.models.importance import Importance
from msgraph.generated.users.item.messages.item.move.move_post_request_body import MovePostRequestBody
from app.agents.base import EmailAgent
from app.microsoftGraph import email as graph


class MicrosoftGraphAgent(EmailAgent):
    def __init__(self, client):
        self.client = client
        self.credential = getattr(client, "email_sifting_credential", None)
        self.http_client = getattr(client, "email_sifting_http_client", None)

    @classmethod
    def authenticate(cls):
        agent = cls(graph.authenticate())
        agent.mailbox_key = agent.client.email_sifting_mailbox_key
        return agent

    def logout(self):
        graph.logout()
        if self.credential is not None:
            self.credential.close()
            self.credential = None

    async def close(self):
        if self.http_client is not None:
            await self.http_client.aclose()
            self.http_client = None
        if self.credential is not None:
            self.credential.close()
            self.credential = None
        self.client = None

    async def list_destinations(self):
        folders = {}

        async def visit(builder, prefix=""):
            response = await builder.get()
            while response:
                for folder in response.value or []:
                    name = prefix + folder.display_name
                    folders[name] = folder.id
                    if folder.child_folder_count:
                        await visit(self.client.me.mail_folders.by_mail_folder_id(folder.id).child_folders, name + "/")
                if not response.odata_next_link:
                    break
                response = await builder.with_url(response.odata_next_link).get()

        await visit(self.client.me.mail_folders)
        self._destinations = folders
        return folders

    async def validate_destinations(self, destinations):
        # Resolve well-known aliases too: a folder may be unavailable in an account.
        known = {"archive", "inbox", "deleteditems", "drafts", "junkemail", "sentitems"}
        if set(destinations) - known:
            await super().validate_destinations(set(destinations) - known)
        for destination in set(destinations) & known:
            folder = await self.client.me.mail_folders.by_mail_folder_id(destination).get()
            if folder is None or not folder.id:
                raise ValueError(f"Microsoft folder is unavailable: {destination}")

    async def get_emails(self, received_after=None, max_emails=100, **kwargs):
        if max_emails < 1:
            raise ValueError("max_emails must be positive")
        return await graph.getEmails(self.client, received_after, max_emails, **kwargs)

    async def delete(self, email):
        return await self.client.me.messages.by_message_id(email.id).delete()

    async def move(self, email, destination):
        destination = getattr(self, "_destinations", {}).get(destination, destination)
        from kiota_abstractions.base_request_configuration import RequestConfiguration
        configuration = RequestConfiguration()
        configuration.headers.add("Prefer", 'IdType="ImmutableId"')
        result = await self.client.me.messages.by_message_id(email.id).move.post(
            MovePostRequestBody(destination_id=destination), request_configuration=configuration)
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
