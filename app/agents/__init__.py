"""Mailbox provider implementations."""
from app.agents.base import EmailAgent


def as_agent(client):
    """Accept legacy Graph clients at the public API boundary."""
    if isinstance(client, EmailAgent):
        return client
    from app.agents.microsoft import MicrosoftGraphAgent
    return MicrosoftGraphAgent(client)


async def getEmails(client, *args, **kwargs):
    return await as_agent(client).get_emails(*args, **kwargs)
