import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def call_llm(messages, model="gpt-4o-mini"):

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0
    )

    return response.choices[0].message.content.strip()