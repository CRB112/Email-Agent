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
        await g_client.me.messages.by_message_id(email.id).delete() 

MODIFY_CLASSES = {
    "Delete" : Delete
}