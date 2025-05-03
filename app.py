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
        "Kobe Bryant", "Michael Jordan", "LeBron James", "Muhammad Ali", "Tom Brady", "Usain Bolt", "Michael Phelps", "Tiger Woods", "Rafael Nadal", "Roger Federer", "Eliud Kipchoge", "Conor McGregor", "Mike Tyson", "Johan Cruyff"
    ]

    entrepreneurs = [
        "Steve Jobs", "Naval Ravikant", "Paul Graham", "Elon Musk", "Walt Disney", "Alex Hormozi", "Walt Disney", "Phil Knight", "David Ogilvy", "Goerge Lucas", "Edwin Catmull", "Thomas Edison", "Phil Jackson", "Jeff Bezos", "James Dyson", "Bill Hewitt", "Peter Thiel", "Levi Strauss", "Edwin Land", "Ray Dalio", "Richard Branson", "Marc Andreessen", "Cornelius Vanderbilt", "Herb Kelleher", "John Bogle", "Howard Hughes", "Yvon Chouinard", "Malcolm McLean", "Benjamin Franklin", "Marc Rich", "Coco Chanel", "Kirk Kerkorian", "Henry Kaiser", "Conrad Hilton", "Daniel Ludwig", "Charles Goodyear", "Stan Lee", "Andrew Carnegie", "Charlie Munger", "Henry Royce", "Thomas J. Watson", "Warren Buffet", "Henry Singleton", "Enzo Ferrari", "Carrol Shelby", "Bill Walsh", "Sol Price", "Frank Lloyd Wright", "Chung Ju-yung", "the Wright brothers", "the Dodge brothers", "Billy Durant", "Albert Champion", "Larry Ellison", "Henry Leland", "Walter Chrysler", "Estee Lauder", "Alexander Graham Bell", "J.P. Morgan", "Bill Gates", "Arnold Schwarzenegger", "Ernest Shackleton", "William Randolph Hearst", "Milton Hershey", "Sam Colt", "Frederick Smith", "Katherin Graham", "Bill Bowerman", "Charles Schulz", "Andy Grove", "Dr. Seuss", "Chuch Yeager", "Jony Ive", "Isadore Sharp", "Jim Casey", "Isambard Kingdom Brunel", "Michael Dell", "Steven Spielberg", "Stephen King", "Paul Van Doren", "Siggi Wilzig", "Charles de Gaulle", "Michael Bloomberg", "Sidney Harman", "William Rosenberg", "Jay Z", "Kanye West", "Harry Snyder", "Rick Rubin", "Mark Leonard", "Socrates", "Henry Goldman", "Jimi Hendrix", "Paul Orfalea", "Ralph Lauren", "Brunello Cucinelli", "David Packard", "Ray Krock", "Rose Blumkin", "James Cameron", "Christopher Nolan", "L'Ebe Bugatti", "Alistar Urquhart", "Sam Zemurray", "Ted Turner", "Les Schwab", "Christian Dior", "Dietrich Mateschitz", "Brad Jacobs", "Quentin Tarantino", "Hans Wilsdorf", "John Mackey", "Sam Zell", "Jensen Huang", "Jerry Jones", "Todd Graves", "Akio Morita"
    ]

    religion = [
        "the Bible", "the Tanakh", "the Quran"
    ]

    misc = [
        "David Goggins", "Jordan Peterson", "Jocko Willink",

        # philosophers
        "Aurelius", "Seneca The Younger", "Epitetus", "Cato The Younger", "Zeno of Citium", "Cleanthes", "Hecato of Rhodes", "Gaius Musonius Rufus", "Socrates", "Confucius", "Plato", "Aristotle", "Friedrich Nietzsche", "Jean-Jacques Rousseau", "Arthur Schopenhauer",

        # authors
        "Mark Twain", "Ralph Waldo Emerson", "Henry David Thoreau", "Paulo Coehlo", "Haruki Murakami", "James Clear", "Brene Brown", "Robin Sharma", "Og Mandino"

        # military
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

    first_adjectives = [
        "motivational", "inspirational", "powerful", "profound"
    ]

    random_first_adjective = random.choice(first_adjectives)

    second_adjectives = [
        "discipline", "perseverance", "grit", "tenacity", "work ethic", "sacrifice", "dedication", "endurance"
    ]

    random_second_adjective = random.choice(second_adjectives)

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
                    "content": f"Give me a short, {random_first_adjective} quote from {random_person} about self improvement that highlights {random_second_adjective}. Do not return a quote about war and do not include any interpretations."
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
