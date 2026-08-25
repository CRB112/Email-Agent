
# PARENT
class Match:
    def __init__(self, settings: dict):
        pass

    def testMatch(self, email) -> bool:
        pass



class Match_sub(Match):
    def __init__(self, settings: dict):
        self.sub = settings.get("Sub")

    def testMatch(self, email) -> bool:
        print("ASDkjdsaflkjfdz")
        return email.subject == self.sub
        
class Match_sender:
    def __init__(self, settings : dict):
        self.sender = settings["Sender"]

    def testMatch(self, email) -> bool:
        print ("BBBBBBBBBB")
        return email.from_.email_adress.address

COMMAND_CLASSES = {
    "match_subject" : Match_sub,
    "match_sender" : Match_sender,
}