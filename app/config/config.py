def getPrompt():
    with open("app/config/config.txt", 'r', encoding='utf-8') as f:
        prompt = f.read()
    return prompt
