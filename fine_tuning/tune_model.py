import os
import sys
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.config import settings

def start_tuning():
    """Start Gemini fine-tuning job using google-generativeai."""
    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: google-generativeai is not installed.")
        return

    if not settings.GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in environment.")
        return

    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'planner_tuning_data.jsonl')
    if not os.path.exists(data_path):
        print(f"Error: Dataset not found at {data_path}. Run prepare_dataset.py first.")
        return
        
    training_data = []
    with open(data_path, 'r') as f:
        for line in f:
            if line.strip():
                training_data.append(json.loads(line))
                
    print(f"Loaded {len(training_data)} training examples.")
    
    # We will tune gemini-1.5-flash as it supports fine tuning.
    base_model = "models/gemini-1.5-flash-001-tuning"
    
    print(f"Starting tuning job for {base_model}...")
    
    try:
        operation = genai.create_tuning_job(
            display_name="retailpulse-planner-tuned",
            source_model=base_model,
            training_data=training_data,
            epoch_count=5,
            batch_size=4,
            learning_rate=0.001,
        )
        
        print(f"Tuning job created successfully!")
        print(f"Job Name: {operation.name}")
        
        # We can wait for it or just return
        print("You can check status using google.generativeai SDK.")
        
        print("\nNOTE: Since fine-tuning takes time, you should save this tuned model name.")
        print("Once complete, update your .env file with:")
        print("MODEL_MODE=tuned")
        print("TUNED_GEMINI_MODEL=tunedModels/your-tuned-model-id")
        
    except Exception as e:
        print(f"Error starting tuning job: {e}")
        print("Note: Fine-tuning requires appropriate Google Cloud / Vertex AI permissions or API enabled for the Google AI Studio project.")

if __name__ == "__main__":
    start_tuning()
