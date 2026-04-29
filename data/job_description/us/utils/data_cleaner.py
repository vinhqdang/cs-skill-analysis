import re


def clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return text.strip()


def clean_job_entry(job: dict) -> dict:
    return {
        key: clean(str(value)) if isinstance(value, str) else (value or "")
        for key, value in job.items()
    }