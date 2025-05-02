from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import random
from typing import Optional

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a FastAPI app
app = FastAPI()

# uvicorn app:app --reload

class ChatResponse(BaseModel):
    quote: str
    source: str

@app.post("/quote")
async def chat_with_openai(topic: str, user_religion: Optional[str] = None):
    print(topic)
    print(user_religion)

    # Define prompt
    sports = [
        "Kobe Bryant", "Michael Jordan", "LeBron James", "Muhammad Ali", "Tom Brady", "Usain Bolt", "Michael Phelps", "Tiger Woods", "Rafael Nadal", "Roger Federer", "Eliud Kipchoge", "Conor McGregor", "Mike Tyson"
    ]

    entrepreneurs = [
        "Steve Jobs", "Naval Ravikant", "Paul Graham", "Elon Musk", "Walt Disney", "Alex Hormozi", "Walt Disney", "Phil Knight", "David Ogilvy"
    ]

    religion = [
        "the Bible", "the Tanakh", "the Quran"
    ]

    misc = [
        "David Goggins", "Jordan Peterson", "Jocko Willink",

        "Aurelius", "Seneca The Younger", "Epitetus", "Cato The Younger", "Zeno of Citium", "Cleanthes", "Hecato of Rhodes", "Gaius Musonius Rufus", "Socrates",

        "Winston Churchill", "Julius Caesar", "Alexander The Great", "Dwight D. Eisenhower", "Napoleon Bonaparte", "George S. Patton", "Ulysses S. Grant", "Theodore Roosevelt", "John F. Kennedy"
    ]

    topic_list = misc

    match topic:
        case "sports":
            topic_list = sports
        case "entrepreneurship":
            topic_list = entrepreneurs
        
    random_person = random.choice(topic_list)

    if topic == "religion" and user_religion != None:
        if user_religion == "christianity" or user_religion == "catholicism":
            random_person = religion[0]
        elif user_religion == "judaism":
            random_person = religion[1]
        elif user_religion == "islam":
            random_person = religion[2]

    adjectives = [
        "discipline", "perseverance", "grit", "tenacity", "work ethic", "sacrifice", "dedication", "endurance"
    ]

    random_adjective = random.choice(adjectives)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "developer", 
                    "content": "You're an expert in successful athletes, entrepreneurs, motivational speakers, and historical figures."
                },
                {
                    "role": "user", 
                    "content": f"Give me a short, inspirational quote from {random_person} that highlights {random_adjective}. Do not return a quote about war and do not include any interpretations."
                }
            ],
            temperature=0.9,
            top_p=0.95,
            response_format=ChatResponse
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        return {"error": str(e)}
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
