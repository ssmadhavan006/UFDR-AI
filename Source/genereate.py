from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

from dotenv import load_dotenv, find_dotenv
import os

print("Looking for .env at:", find_dotenv())  # Debug
load_dotenv()

print("GOOGLE_API_KEY from env:", os.getenv("GOOGLE_API_KEY"))  # Debug

# Load API key from .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

# Use Gemini 1.5 Flash (free tier in AI Studio)
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    api_key=api_key   # ✅ correct param
)

response = llm.invoke("Hello, are you working?")
print(response.content)
