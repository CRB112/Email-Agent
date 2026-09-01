
from abc import ABC, abstractmethod


class Match(ABC):
    @abstractmethod
    def testMatch(self, email) -> bool:
        """Return whether an email satisfies this matcher."""
        raise NotImplementedError



class Match_subject(Match):
    def __init__(self, settings: dict):
        self.sub = settings.get("Sub")

    def testMatch(self, email) -> bool:
        return email.subject == self.sub

        

class Match_sender(Match):
    def __init__(self, settings : dict):
        self.sender = settings["Sender"]

    def testMatch(self, email) -> bool:
        address = email.from_.email_address.address
        return address.strip().lower() == self.sender.strip().lower()

class Match_domain(Match):
    def __init__(self, settings : dict):
        self.domain = settings["Domain"]

    def testMatch(self, email) -> bool:
        address = email.from_.email_address.address.strip().lower()
        try:
            _, domain = address.rsplit("@", 1)
        except ValueError:
            return False
        return domain == self.domain.strip().lower()

class Match_contains(Match, ABC):
    def __init__(self, settings: dict):
        self.words = settings["Words"]
        self.match_type = settings.get("Type", "All").lower()
        self.case_sensitive = settings.get("CaseSensitive", False)

        if self.match_type not in {"any", "all"}:
            raise ValueError("Type must be either 'Any' or 'All'")

    @abstractmethod
    def get_search_text(self, email) -> str:
        """Extract the text that this child matcher searches."""
        raise NotImplementedError

    def testMatch(self, email) -> bool:
        text = self.get_search_text(email) or ""
        words = self.words

        if not self.case_sensitive:
            text = text.casefold()
            words = [word.casefold() for word in words]

        matches = (word in text for word in words)
        return any(matches) if self.match_type == "any" else all(matches)

class Match_body_contains(Match_contains):
    def get_search_text(self, email) -> str:
        return email.body.content if email.body and email.body.content else ""


class Match_subject_contains(Match_contains):
    def get_search_text(self, email) -> str:
        return email.subject or ""


class Match_sender_contains(Match_contains):
    def get_search_text(self, email) -> str:
        if not email.from_ or not email.from_.email_address:
            return ""
        return email.from_.email_address.address or ""



COMMAND_CLASSES = {
    "match_subject" : Match_subject,
    "match_sender" : Match_sender,
    "match_domain" : Match_domain,
    # Keep the old name so previously saved rules continue to work.
    "match_body" : Match_body_contains,
    "match_body_contains" : Match_body_contains,
    "match_subject_contains" : Match_subject_contains,
    "match_sender_contains" : Match_sender_contains
}