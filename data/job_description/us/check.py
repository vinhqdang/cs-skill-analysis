import pandas as pd

df = pd.read_csv('data/us_jobs_raw.csv')
print(f"Total jobs: {len(df)}")
print(f"\nBy source:")
print(df['source'].value_counts())
print(f"\nEmpty job_id: {df['job_id'].isna().sum()}")
print(f"Empty url: {df['url'].isna().sum()}")
print(f"Duplicate urls: {df.duplicated(subset='url').sum()}")