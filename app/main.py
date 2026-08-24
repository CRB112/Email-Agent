import os
from dotenv import load_dotenv
from google import genai
from config.config import getPrompt

load_dotenv()

def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chat = client.chats.create(model="gemini-3.6-flash",
                               config={'system_instruction' : getPrompt()})

    msg = input("What would you like to say?")

    response = chat.send_message(msg)

    print(response.text)
if __name__ == "__main__":
    main()