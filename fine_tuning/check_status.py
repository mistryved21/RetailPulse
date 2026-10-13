import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.config import settings

def check_tuning_status():
    """Check status of Gemini fine-tuning jobs."""
    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: google-generativeai is not installed.")
        return

    if not settings.GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in environment.")
        return

    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    try:
        print("Fetching tuning jobs...")
        jobs = list(genai.list_tuned_models())
        if not jobs:
            print("No tuned models found.")
        else:
            for job in jobs:
                print(f"Name: {job.name}")
                print(f"Base Model: {job.base_model}")
                print(f"State: {job.state}")
                print(f"Create Time: {job.create_time}")
                print("-" * 30)
    except Exception as e:
        print(f"Error fetching jobs: {e}")

if __name__ == "__main__":
    check_tuning_status()
