import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
import google.generativeai as genai

# ----------------- Load environment & configure Gemini ------------------
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.5-pro")

# ----------------- Memory & History Setup ------------------
memory = ConversationBufferMemory(return_messages=True)
HISTORY_FILE = "chat_history.json"

# ✨ Default static memory (user profile or facts)
DEFAULT_HISTORY = [
    {"user": "My name is Mizan.", "bot": "Nice to meet you, Mizan!"},
    {"user": "My favorite sport is football.", "bot": "That's great! Football is an exciting game."},
    {"user": "I support Argentina.", "bot": "Argentina has a fantastic football team!"}
]

# Prompt template
prompt_template = PromptTemplate(
    input_variables=["chat_history", "human_input"],
    template="You are a helpful assistant.\n\n{chat_history}\nHuman: {human_input}\nAssistant:"
)

# Load chat history from JSON
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

# Save new chat turn to JSON
def save_to_json(user, bot):
    history = load_history()
    history.append({"user": user, "bot": bot})
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# Load both default facts + previous chat into memory
def load_chat_to_memory():
    for entry in DEFAULT_HISTORY:
        memory.save_context({"input": entry["user"]}, {"output": entry["bot"]})
    previous_chats = load_history()
    for entry in previous_chats:
        memory.save_context({"input": entry["user"]}, {"output": entry["bot"]})

# Main chat function
def chat_with_bot(user_input: str) -> str:
    history = memory.load_memory_variables({})["history"]
    formatted_prompt = prompt_template.format(chat_history=history, human_input=user_input)

    try:
        response = model.generate_content([formatted_prompt])
        reply = response.text.strip()
        memory.save_context({"input": user_input}, {"output": reply})
        save_to_json(user_input, reply)
        return reply
    except Exception as e:
        print("Gemini error:", e)
        return "Sorry, something went wrong."


# ----------------- FastAPI App Setup ------------------
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Load memory on startup
load_chat_to_memory()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat_api(message: str = Form(...)):
    response = chat_with_bot(message)
    return JSONResponse(content={"user": message, "bot": response})
