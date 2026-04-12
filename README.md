# CS Curriculum Skills Gap Analysis

This project aims to build a skills demand dataset to inform the design of a new Computer Science undergraduate program.

## Setup Instructions

### Environment
The project relies on a Conda environment with Python 3.13 and CUDA enabled on an Nvidia GPU.

To create and activate the environment (if you haven't already):
```bash
conda create -n py313 python=3.13
conda activate py313
```

Install the required dependencies:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Collaborator Instructions & Directory Structure

To keep the repository clean and maintainable, please follow these guidelines when contributing:

1. **`code/`**: All your source code belongs here.
   - **`code/scrapper/`**: Place all data gathering and web scraping scripts here.
   - **`code/analytics/`**: Place all analytics, modeling, and data processing scripts here.
   
2. **`data/`**: Keep data meticulously organized. 
   - **`data/job_description/`**: Store job market data here.
   - **`data/education_program/`**: Store university program/curriculum data here.
   - **Country-Specific Folders**: Inside both `job_description` and `education_program`, place your data in the respective country folders:
     - `/us/`
     - `/uk/`
     - `/singapore/`
     - `/vn/`
     - Create a new explicit country folder if your target region isn't listed above.

3. **`manuscripts/`**: All drafts, papers, and TeX documents associated with publications should be kept in this directory.

**Important:** Please ensure you only commit to the correct directories according to the structure above. 

## Git Instructions
- Always push code to the `main` branch after modification.
- Make sure to document any new dependencies in `requirements.txt`.
