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
async def chat_with_openai(topic: str):
    print(topic)

    # Define prompt
    sports = [
        "Kobe Bryant", "Michael Jordan", "LeBron James", "Muhammad Ali", "Tom Brady", "Usain Bolt", "Michael Phelps", "Tiger Woods", "Rafael Nadal", "Roger Federer", "Eliud Kipchoge", "Conor McGregor", "Mike Tyson", "Johan Cruyff", "Laird Hamilton", "Willie Mays", "Vince Lombardi", "Bobby Knight", "Wayne Gretzky", "John Wooden"
    ]

    entrepreneurs = [
        "Steve Jobs", "Naval Ravikant", "Paul Graham", "Elon Musk", "Walt Disney", "Alex Hormozi", "Walt Disney", "Phil Knight", "David Ogilvy", "Goerge Lucas", "Edwin Catmull", "Thomas Edison", "Phil Jackson", "Jeff Bezos", "James Dyson", "Bill Hewitt", "Peter Thiel", "Levi Strauss", "Edwin Land", "Ray Dalio", "Marc Andreessen", "Howard Hughes", "Yvon Chouinard", "Malcolm McLean", "Benjamin Franklin", "Henry Kaiser", "Conrad Hilton", "Andrew Carnegie", "Charlie Munger", "Henry Royce", "Thomas J. Watson", "Enzo Ferrari", "Bill Walsh", "Chung Ju-yung", "Billy Durant", "Alexander Graham Bell", "J.P. Morgan", "Bill Gates", "Arnold Schwarzenegger", "Ernest Shackleton", "Milton Hershey", "Sam Colt", "Bill Bowerman", "Andy Grove", "Chuck Yeager", "Isadore Sharp", "Jim Casey", "Michael Dell", "Stephen King", "Michael Bloomberg", "William Rosenberg", "Rick Rubin", "Ray Krock", "James Cameron", "Sam Zell", "Jensen Huang", "Jerry Jones", "Akio Morita", "Charles Kettering",
    ]

    misc = [
        "David Goggins", "Jordan Peterson", "Jocko Willink",

        # philosophers
        "Aurelius", "Seneca The Younger", "Epitetus", "Cato The Younger", "Zeno of Citium", "Hecato of Rhodes", "Gaius Musonius Rufus", "Socrates", "Confucius", "Plato", "Aristotle", "Friedrich Nietzsche", "Jean-Jacques Rousseau", "Arthur Schopenhauer", "Lao Tzu", "Carl Jung",

        # authors
        "Mark Twain", "Ralph Waldo Emerson", "Henry David Thoreau", "Paulo Coehlo", "Haruki Murakami", "James Clear", "Brene Brown", "Robin Sharma", "Og Mandino", "Shakespeare", "Alexander Pope", "William Arthur Ward", 

        # military
        "Winston Churchill", "Julius Caesar", "Alexander The Great", "Dwight D. Eisenhower", "Napoleon Bonaparte", "George S. Patton", "Ulysses S. Grant", "Theodore Roosevelt", "John F. Kennedy", "Hannibal"
    ]

    topic_list = misc

    match topic:
        case "sports":
            topic_list = sports
        case "entrepreneurship":
            topic_list = entrepreneurs
        
    random_person = random.choice(topic_list)

    first_adjectives = [
        "motivational", "inspirational", "powerful", "profound"
    ]

    random_first_adjective = random.choice(first_adjectives)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "developer", 
                    "content": "You're an expert in successful athletes, entrepreneurs, authors, philosophers, public figures, and historical figures."
                },
                {
                    "role": "user", 
                    "content": f"Give me a random, short, {random_first_adjective} quote from {random_person} about life. Do not quote someone else, return a quote about war, include quotation marks, or include any interpretations."
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
