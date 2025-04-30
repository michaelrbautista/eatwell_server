from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import random

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a FastAPI app
app = FastAPI()

# uvicorn app:app --reload

class ChatResponse(BaseModel):
    quote: str
    person: str

@app.post("/quote")
async def chat_with_openai(topic: str):
    # Define prompt
    sports = [
        "Kobe Bryant", "Michael Jordan", "LeBron James", "Muhammad Ali", "Tom Brady", "Brian Dawkins", "Usain Bolt", "Michael Phelps", "Tiger Woods", "Rafael Nadal", "Roger Federer", "Eliud Kipchoge", "Conor McGregor"
    ]

    entrepreneurs = [
        "Steve Jobs", "Naval Ravikant", "Paul Graham", "Elon Musk", "Walt Disney", "Alex Hormozi", "Walt Disney", "Phil Knight", "David Ogilvy"
    ]

    misc = [
        "David Goggins", "Jordan Peterson", "Jocko Willink", "Phil Jackson"

        "Aurelius", "Seneca The Younger", "Epitetus", "Cato The Younger", "Zeno of Citium", "Cleanthes", "Hecato of Rhodes", "Gaius Musonius Rufus", "Socrates",

        "Winston Churchill", "Julius Caesar", "Alexander The Great", "Dwight D. Eisenhower", "Napoleon Bonaparte", "George S. Patton", "Ulysses S. Grant", "Theodore Roosevelt", "John F. Kennedy"
    ]

    topic_list = misc

    match topic:
        case "sports":
            topic_list = sports
        case "entrepreneurship":
            topic_list = entrepreneurs

    person = random.choice(topic_list)

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
                    "content": f"Give me an inspirational quote from {person} that highlights grit and perseverance. Do not include any interpretations."
                }
            ],
            temperature=0.9,
            response_format=ChatResponse
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        return {"error": str(e)}
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
