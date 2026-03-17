import os
import json
import asyncio
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import time
import random

# Load .env variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in the environment or .env file.")

client = genai.Client(api_key=API_KEY)

class JobSkills(BaseModel):
    hard_skills: list[str] = Field(description="Technical skills, programming languages, databases, tools, cloud platforms, etc.")
    soft_skills: list[str] = Field(description="Soft skills, interpersonal skills, communication, leadership, cognitive abilities, or personality traits explicitly required.")

class BatchJobSkills(BaseModel):
    jobs: list[JobSkills] = Field(description="The extracted skills for each job description in the exact order they were provided.")

async def extract_batch_async(batch_text: str, batch_id: int) -> list[dict]:
    """Asynchronously extracts skills using the gemini client for a BATCH of jobs."""
    for attempt in range(5):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model='gemini-3.1-flash-lite-preview',
                contents=f"Extract all technical hard skills AND interpersonal soft skills from these sequentially numbered job descriptions. Return exactly one list item per job description in the same order.\n\n{batch_text}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchJobSkills,
                    temperature=0.1
                ),
            )
            result = json.loads(response.text)
            jobs = result.get("jobs", [])
            return [{"hard_skills": j.get("hard_skills", []), "soft_skills": j.get("soft_skills", [])} for j in jobs]
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "503" in str(e):
                await asyncio.sleep(2 ** attempt * 5)
            else:
                print(f"[Batch {batch_id}] Error: {e}")
                return []
    return []

async def process_batch(jobs_df, chunk_size=30, max_concurrency=3):
    semaphore = asyncio.Semaphore(max_concurrency)
    
    # Chunk jobs
    job_chunks = [jobs_df[i:i + chunk_size] for i in range(0, len(jobs_df), chunk_size)]
    total_chunks = len(job_chunks)
    completed = 0
    
    all_results = []
    
    async def sem_task(chunk, idx):
        nonlocal completed
        async with semaphore:
            batch_text = ""
            for i, row in enumerate(chunk.itertuples()):
                desc = getattr(row, "description")
                # Clean up and limit each description
                clean_desc = str(desc).strip()[:2000] 
                batch_text += f"--- JOB {i+1} ---\n{clean_desc}\n\n"
            
            skills_list = await extract_batch_async(batch_text, idx)
            # Pad with empties if the LLM returned too few
            while len(skills_list) < len(chunk):
                skills_list.append({"hard_skills": [], "soft_skills": []})
                
            completed += 1
            print(f"Progress: {completed}/{total_chunks} chunks ({(completed/total_chunks)*100:.1f}%) processed")
            return skills_list
    
    tasks = [sem_task(chunk, i) for i, chunk in enumerate(job_chunks)]
    chunk_results = await asyncio.gather(*tasks)
    
    for res in chunk_results:
        all_results.extend(res)
        
    return all_results

def main():
    print("Loading datasets...")
    # Load all json files from the directory if they exist and combine
    data_files = [
        "data/raw/job_postings/jobspy_vietnam.json",
        "data/raw/job_postings/jobspy_asia.json",
        "data/raw/job_postings/jobspy_global.json",
        "data/raw/job_postings/itviec.json"
    ]
    
    dfs = []
    for f in data_files:
        try:
            df = pd.read_json(f)
            dfs.append(df)
            print(f"Loaded {len(df)} rows from {f}")
        except FileNotFoundError:
            print(f"File not found or not yet parsed: {f}")
    
    if not dfs:
        print("No datasets available to process.")
        return
        
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Needs valid ID and Description
    # Handle the fact that jobspy outputs 'id' but itviec outputs 'url' as main id
    if "id" not in combined_df.columns and "url" in combined_df.columns:
         combined_df["id"] = combined_df["url"].apply(lambda x: hash(x))
    elif "id" not in combined_df.columns:
        combined_df["id"] = combined_df.index.astype(str)
        
    combined_df["id"] = combined_df.get("id", pd.Series([None]*len(combined_df)))
    combined_df["id"] = combined_df["id"].fillna(pd.Series(combined_df.index).astype(str))
    
    combined_df = combined_df.dropna(subset=["description"])
    # To avoid 12-hour wait times, sample randomly if huge
    if len(combined_df) > 2000:
        print("Sampling 2000 random jobs to meet API constraints...")
        sample_df = combined_df.sample(2000, random_state=42).copy()
    else:
        sample_df = combined_df.copy()
    
    # Run async extraction
    print("Starting LLM extraction...")
    start_time = time.time()
    extracted_skills_list = asyncio.run(process_batch(sample_df, chunk_size=20, max_concurrency=2))
    print(f"Finished extraction in {time.time() - start_time:.2f} seconds.")
    
    # Add to dataframe
    sample_df["hard_skills"] = [res["hard_skills"] for res in extracted_skills_list]
    sample_df["soft_skills"] = [res["soft_skills"] for res in extracted_skills_list]
    
    # Function to calculate frequencies
    def get_freq(df, col_name):
        exploded = df.explode(col_name).dropna(subset=[col_name])
        # remove empty strings
        exploded = exploded[exploded[col_name] != ""]
        freq = exploded.groupby(col_name).size().reset_index(name="job_count")
        freq["demand_pct"] = (freq["job_count"] / len(df)) * 100
        return freq.sort_values("demand_pct", ascending=False)
        
    hard_freq = get_freq(sample_df, "hard_skills")
    soft_freq = get_freq(sample_df, "soft_skills")
    
    print("\nTop 10 Extracted Hard Skills:")
    print(hard_freq.head(10))
    
    print("\nTop 10 Extracted Soft Skills:")
    print(soft_freq.head(10))
    
    # Save the processed data
    os.makedirs("data/processed", exist_ok=True)
    
    hard_freq.to_csv("data/processed/hard_skills_freq.csv", index=False)
    soft_freq.to_csv("data/processed/soft_skills_freq.csv", index=False)
    sample_df.to_json("data/processed/jobs_with_skills_both.json", orient="records", indent=4)
    print("Data saved to data/processed/")

if __name__ == "__main__":
    main()
