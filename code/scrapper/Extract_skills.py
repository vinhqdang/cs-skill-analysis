import pandas as pd
import time
from tqdm import tqdm
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed 

INPUT_FILE = "" 
OUTPUT_FILE = ""
MAX_WORKERS = 10 

client = OpenAI(
    base_url="",
    api_key="",
    timeout=60.0 
)
ROUTER_MODEL_NAME = ""


def extract_single_skill(description):
    
    system_prompt = """
    You are a Lead Data Engineer building a highly granular skills taxonomy for the Tech industry. 
    Extract a comma-separated list of SPECIFIC technical, analytical, and professional skills from the course description.
    
    CRITICAL RULE: Extract SPECIFIC languages, tools, and paradigms (e.g., 'Python', 'Object-Oriented Programming', 'C++') rather than generalizing them into broad terms like 'Programming'.
    
    ALLOWED DOMAINS (Extract these):
    1. Software, Data & Security: Specific Programming Languages (Python, Java, C++, R...), Software Paradigms (Object-Oriented Programming, etc.), AI/Machine Learning, Data Science, Cybersecurity, Cryptography, Databases, Algorithms, Optimization, Simulation, Statistical Modeling.
    2. Hardware & IoT: Embedded Systems, Electrical Engineering, Circuit Design, Sensors, Signal Processing.
    3. Product & Design: UI/UX Design, Human-Computer Interaction (HCI), Product Management.
    4. Research & Professional: Research Methods, Technical Writing, Thesis/Academic Writing, Oral Presentations, Tech Ethics, Intellectual Property (IP), Patent Law.
    
    RULES:
    1. Output ONLY a comma-separated list of skills. 
    2. DO NOT output JSON. DO NOT write introductory text.
    3. If absolutely no relevant skills are found, output exactly the word "None".
    """
    
    try:
        response = client.chat.completions.create(
            model=ROUTER_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Description: {description}"}
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"ERROR_TIMEOUT_OR_CRASH"


def process_row(idx, desc):
    skill = extract_single_skill(desc)
    return idx, skill


if __name__ == "__main__":
    print("Loading")
    df = pd.read_csv(INPUT_FILE)
    
    if 'skills_gained' not in df.columns:
        df['skills_gained'] = None
        
    mask = df['description'].notnull() & (df['skills_gained'].isnull() | df['skills_gained'].astype(str).str.contains("ERROR"))
    indices_to_process = df[mask].index.tolist()
    
    total = len(indices_to_process)
    print(f"Rows: {total}")
    
    if total == 0:
        print("Completed")
        exit()

    print(f"Multi threads: {MAX_WORKERS} Threads...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {executor.submit(process_row, idx, df.at[idx, 'description']): idx for idx in indices_to_process}
        for count, future in enumerate(tqdm(as_completed(future_to_idx), total=total, desc="Extracting Skills")):
            idx = future_to_idx[future]
            try:
                returned_idx, skill = future.result()
                df.at[returned_idx, 'skills_gained'] = skill
            except Exception as exc:
                df.at[idx, 'skills_gained'] = "ERROR_MULTI_THREAD"
            
            if (count + 1) % 50 == 0:
                df.to_csv(OUTPUT_FILE, index=False)
                

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved at: {OUTPUT_FILE}")