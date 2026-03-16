# CS Curriculum Skills Gap Analysis

This project aims to build a skills demand dataset to inform the design of a new Computer Science undergraduate program, focusing on the Vietnamese, Southeast Asian, and global markets.

## Setup Instructions

### Environment
The project relies on a Conda environment with Python 3.13. 

To create and activate the environment:
```bash
conda create -n py313 python=3.13
conda activate py313
```

Install the required dependencies:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Directory Structure
- `data/` - Contains raw, processed, and framework data.
- `scrapers/` - Custom scraping scripts (`jobspy_scraper.py`, `itviec_scraper.py`, `vietnamworks_scraper.py`).
- `notebooks/` - Jupyter notebooks for analysis (to be implemented).

## Job Scrapers

The project includes three distinct scrapers to collect job postings:
1. **JobSpy Scraper** (`scrapers/jobspy_scraper.py`): Scrapes LinkedIn, Indeed, and Google Jobs using `python-jobspy`.
2. **ITviec Scraper** (`scrapers/itviec_scraper.py`): Custom scraper for ITviec, targeting specific programming keywords.
3. **VietnamWorks Scraper** (`scrapers/vietnamworks_scraper.py`): Custom scraper utilizing the VietnamWorks Algolia API (or HTML fallback) to extract job listings.

Run the scrapers individually:
```bash
python scrapers/jobspy_scraper.py
python scrapers/itviec_scraper.py
python scrapers/vietnamworks_scraper.py
```

## Work Plan
Detailed project timeline, data collection targets, and step-by-step methodologies are outlined in the [`work_plan.md`](work_plan.md) document.
