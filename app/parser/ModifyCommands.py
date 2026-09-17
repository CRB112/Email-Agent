from app.agents import as_agent


class Modify:
    def __init__(self, settings : dict):
        if settings is None:
            self.settings = {}
        else:
            self.settings = settings
    async def modify(self, email, g_client):
        raise NotImplementedError

class Delete(Modify):
    def __init__(self, settings : dict):
        super().__init__(settings)
    async def modify(self, email, g_client):
        return await as_agent(g_client).delete(email)

class Move(Modify):
    def __init__(self, settings : dict):
        super().__init__(settings)
        self.dest = settings["Folder"]
    async def modify(self, email, g_client):
        return await as_agent(g_client).move(email, self.dest)

class Mark(Modify):
    def __init__(self, settings : dict):
        super().__init__(settings)
        self.markType = settings["Mark_type"]
        default_op = "Read" if self.markType == "Read" else "Normal"
        self.markOp = settings.get("Mark_op", default_op)
    async def modify(self, email, g_client):
        return await as_agent(g_client).mark(email, self.markType, self.markOp)



MODIFY_CLASSES = {
    "Delete" : Delete,
    "Move" : Move,
    "Mark" : Mark
}
