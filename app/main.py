import asyncio
import os
from dotenv import load_dotenv
from google import genai

from config.config import getPrompt
from microsoftGraph.email import getEmails
from parser.parser import parseEmailsWithJson

load_dotenv()

def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chat = client.chats.create(model="gemini-3.6-flash",
                               config={'system_instruction' : getPrompt()})

    emails = asyncio.run(getEmails())
    parseEmailsWithJson(emails)

if __name__ == "__main__":
    main()
