import os
import json
import asyncio
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Load .env variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set.")

client = genai.Client(api_key=API_KEY)

class CurriculumSkills(BaseModel):
    skills: list[str] = Field(description="A list of technical skills, programming languages, databases, computer science concepts, design patterns, or software engineering methodologies explicitly taught or mentioned in the curriculum text. Be extremely specific. Convert everything to lowercase.")

def scrape_text(url: str) -> str:
    print(f"Scraping {url} via Jina Reader...")
    jina_url = f"https://r.jina.ai/{url}"
    scraper = cloudscraper.create_scraper()
    try:
        r = scraper.get(jina_url, timeout=30)
        return r.text
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return ""

async def extract_skills_async(text: str, name: str) -> list[str]:
    print(f"[{name}] Extracting skills via LLM...")
    if not text:
        return []
    try:
        # Avoid massive token limits, limit to top 15k chars
        processed_text = text[:15000]
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-3.1-flash-lite-preview',
            contents=f"Extract all technical skills, frameworks, tools, programming languages, and IT methodologies from this computer science university curriculum description:\n\n{processed_text}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CurriculumSkills,
                temperature=0.1
            ),
        )
        
        result = json.loads(response.text)
        skills = result.get("skills", [])
        print(f"[{name}] Extracted {len(skills)} skills.")
        return skills
    except Exception as e:
        print(f"[{name}] Error: {e}")
        return []

async def process_curriculums():
    with open("data/raw/curriculums/targets.json", "r") as f:
        targets = json.load(f)
        
    results = []
    
    # Normally we do gather, but since there are only 6 universities, sequential or semi-parallel is fine
    for target in targets:
        text = scrape_text(target["url"])
        if text:
            skills = await extract_skills_async(text, target["university"])
            target["extracted_skills"] = skills
            target["text_length"] = len(text)
        else:
            target["extracted_skills"] = []
            target["text_length"] = 0
            
        results.append(target)
        
    # Flatten
    flattened = []
    for r in results:
        for s in r["extracted_skills"]:
            flattened.append({
                "university": r["university"],
                "region": r["region"],
                "skill": s
            })
            
    df = pd.DataFrame(flattened)
    
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv("data/processed/curriculum_skills.csv", index=False)
    print("Saved skill mapping to data/processed/curriculum_skills.csv")

if __name__ == "__main__":
    asyncio.run(process_curriculums())
