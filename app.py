from fastapi import FastAPI
from openai import OpenAI
import uvicorn
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import random
from supabase import create_client, Client

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a FastAPI app
app = FastAPI()

# source venv/bin/activate
# uvicorn app:app --reload

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))




class QuoteResponse(BaseModel):
    quote: str
    source: str

@app.post("/quote")
async def get_quote(topic: str):
    response = supabase.rpc("get_random_quote").execute()
    
    data = response.data

    if not data:
        return {"error": "Couldn't get response."}
    
    return QuoteResponse(**data[0])




class FeedQuotes(BaseModel):
    quotes: list[QuoteResponse]

@app.post("/feed")
async def get_quote():
    response = supabase.rpc("get_five_random_quotes").execute()
    
    data = response.data

    if not data:
        return {"error": "Couldn't get response."}
    
    return FeedQuotes(quotes=data)




class EmergencyResponse(BaseModel):
    content: str

@app.post("/emergency")
async def chat_with_openai():

    adjectives = [
        "discipline", "grit", "perseverance", "self-control", "willpower", "determination", "reslience", "commitment", "consistency", "accountability", "adversity", "sacrifice"
    ]

    adjective = random.choice(adjectives)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "developer", 
                    "content": "You're an expert in motivation and self improvement."
                },
                {
                    "role": "user", 
                    "content": f"Tell me something about {adjective} so harsh that it will break my heart and also make me attack my goals. Keep it 2-3 sentences."
                }
            ],
            temperature=0.9,
            top_p=0.95,
            response_format=EmergencyResponse
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        return {"error": str(e)}




@app.post("/gpt")
async def chat_with_openai(topic: str):
    print(topic)

    # Define prompt
    sports = [
        "Kobe Bryant", "Michael Jordan", "LeBron James", "Muhammad Ali", "Tom Brady", "Usain Bolt", "Michael Phelps", "Tiger Woods", "Rafael Nadal", "Roger Federer", "Eliud Kipchoge", "Conor McGregor", "Mike Tyson", "Johan Cruyff", "Laird Hamilton", "Willie Mays", "Vince Lombardi", "Bobby Knight", "Wayne Gretzky", "John Wooden"
    ]

    entrepreneurs = [
        "Steve Jobs", "Naval Ravikant", "Paul Graham", "Elon Musk", "Alex Hormozi", "Walt Disney", "Phil Knight", "David Ogilvy", "George Lucas", "Edwin Catmull", "Thomas Edison", "Phil Jackson", "Jeff Bezos", "James Dyson", "Bill Hewitt", "Peter Thiel", "Levi Strauss", "Edwin Land", "Ray Dalio", "Marc Andreessen", "Howard Hughes", "Yvon Chouinard", "Malcolm McLean", "Benjamin Franklin", "Henry Kaiser", "Conrad Hilton", "Andrew Carnegie", "Charlie Munger", "Henry Royce", "Thomas J. Watson", "Enzo Ferrari", "Bill Walsh", "Chung Ju-yung", "Billy Durant", "Alexander Graham Bell", "J.P. Morgan", "Bill Gates", "Arnold Schwarzenegger", "Ernest Shackleton", "Milton Hershey", "Sam Colt", "Bill Bowerman", "Andy Grove", "Chuck Yeager", "Isadore Sharp", "Jim Casey", "Michael Dell", "Stephen King", "Michael Bloomberg", "William Rosenberg", "Rick Rubin", "Ray Krock", "James Cameron", "Sam Zell", "Jensen Huang", "Jerry Jones", "Akio Morita", "Charles Kettering",
    ]

    misc = [
        "David Goggins", "Jordan Peterson", "Jocko Willink", "Virgil Abloh", "Jim Rohn", "Brian Tracy",

        # philosophers
        "Aurelius", "Seneca The Younger", "Epictetus", "Cato The Younger", "Zeno of Citium", "Hecato of Rhodes", "Gaius Musonius Rufus", "Socrates", "Confucius", "Plato", "Aristotle", "Friedrich Nietzsche", "Jean-Jacques Rousseau", "Arthur Schopenhauer", "Lao Tzu", "Carl Jung",

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
        "motivational", "inspirational"
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
                    "content": f"Give me a random, {random_first_adjective} quote from {random_person} about self improvement. Do not quote someone else, do not return a quote about war, do not include quotation marks, and do not include any interpretations."
                }
            ],
            temperature=0.9,
            top_p=0.95,
            response_format=QuoteResponse
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        return {"error": str(e)}
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
