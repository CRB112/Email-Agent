from msgraph.generated.users.item.messages.item.move.move_post_request_body import (
    MovePostRequestBody,
)
from msgraph.generated.models.message import Message
from msgraph.generated.models.importance import Importance


class Modify:
    def __init__(self, settings : dict):
        if settings is None:
            self.settings = {}
        else:
            self.settings = settings
    async def modify(self, email, g_client):
        pass

class Delete(Modify):
    def __init__(self, settings : dict):
        super().__init__(settings)
    async def modify(self, email, g_client):
        return await g_client.me.messages.by_message_id(email.id).delete() 

class Move(Modify):
    def __init__(self, settings : dict):
        super().__init__(settings)
        self.dest = settings["Folder"]
    async def modify(self, email, g_client):
        request_body = MovePostRequestBody(destination_id=self.dest)
        
        return await (
            g_client.me.messages
            .by_message_id(email.id)
            .move
            .post(request_body)
        )

class Mark(Modify):
    def __init__(self, settings : dict):
        super().__init__(settings)
        self.markType = settings["Mark_type"]
        default_op = "Read" if self.markType == "Read" else "Normal"
        self.markOp = settings.get("Mark_op", default_op)
    async def modify(self, email, g_client):
        request_body = Message()
        if self.markType == "Read":
            request_body.is_read = self.markOp.lower() == "read"
        elif self.markType == "Importance":
            request_body.importance = Importance(self.markOp.lower())

        return await (
            g_client.me.messages.by_message_id(email.id).patch(request_body)
        )



MODIFY_CLASSES = {
    "Delete" : Delete,
    "Move" : Move,
    "Mark" : Mark
}
