from msgraph.generated.users.item.messages.item.move.move_post_request_body import (
    MovePostRequestBody,
)


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

MODIFY_CLASSES = {
    "Delete" : Delete,
    "Move" : Move
}