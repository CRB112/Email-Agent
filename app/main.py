import asyncio
import os
from dotenv import load_dotenv
from google import genai

from config.config import getPrompt
from microsoftGraph.email import getEmails
from parser.parser import parseEmailsWithJson, parseUserOptions

load_dotenv()

async def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chat = client.chats.create(model="gemini-3.6-flash",
                               config={'system_instruction' : getPrompt()})

    emails = await getEmails()
    parseUserOptions()
    await parseEmailsWithJson(emails)

if __name__ == "__main__":
    asyncio.run(main())
