
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
        return email.subject == self.sub
        
class Match_sender:
    def __init__(self, settings : dict):
        self.sender = settings["Sender"]

    def testMatch(self, email) -> bool:
        return email.from_.email_address.address

class Match_domain:
    def __init__(self, settings : dict):
        self.domain = settings["Domain"]

    def testMatch(self, email) -> bool:
        address = email.from_.email_address.address.strip().lower()
        try:
            _, domain = address.rsplit("@", 1)
        except ValueError:
            return False
        return domain == self.domain

class Match_body:
    def __init__(self, settings : dict):
        self.matchL = settings["Words"]
        self.matchT = settings.get("Type", "All")
    def testMatch(self, email):
        body = email.body.content if email.body and email.body.content else ""
        if self.matchT == "Any":
            for word in self.matchL:
                if word in body:
                    return True
        if self.matchT == "All":
            for word in self.matchT:
                if word not in body:
                    return False
            return True

COMMAND_CLASSES = {
    "match_subject" : Match_sub,
    "match_sender" : Match_sender,
    "match_domain" : Match_domain
}