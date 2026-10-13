import json
import os
import sys

# Add parent directory to path to import RetailPulse modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from prompts.planner_prompt import PLANNER_SYSTEM_PROMPT

def generate_planner_dataset():
    """Generate a synthetic dataset for fine-tuning the Planner Agent."""
    examples = [
        {"input": "Show me total sales by region.", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": false, "needs_email": false, "chart_type": "bar", "description": "Total sales by region"}'},
        {"input": "Can you forecast inventory for the next 3 months?", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": true, "needs_insight": true, "needs_report": false, "needs_email": false, "chart_type": "line", "description": "Forecast inventory for next 3 months"}'},
        {"input": "Generate a PDF report for last week's performance and send it to me.", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": true, "needs_email": true, "chart_type": "auto", "description": "Last week performance report and email"}'},
        {"input": "What are the top 10 best-selling products?", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": false, "needs_email": false, "chart_type": "bar", "description": "Top 10 best-selling products"}'},
        {"input": "How many customers registered today?", "output": '{"needs_sql": true, "needs_visualization": false, "needs_forecast": false, "needs_insight": false, "needs_report": false, "needs_email": false, "chart_type": "auto", "description": "Count of customers registered today"}'},
        {"input": "Compare revenue for electronics vs clothing over the last year.", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": false, "needs_email": false, "chart_type": "line", "description": "Compare revenue electronics vs clothing last year"}'},
        {"input": "I need a breakdown of payment methods used in Q1.", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": false, "needs_email": false, "chart_type": "pie", "description": "Breakdown of payment methods in Q1"}'},
        {"input": "What's the relationship between product cost and sales volume?", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": false, "needs_email": false, "chart_type": "scatter", "description": "Relationship between cost and sales volume"}'},
        {"input": "Show me the distribution of customer ages.", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": false, "needs_email": false, "chart_type": "histogram", "description": "Distribution of customer ages"}'},
        {"input": "Send a sales overview to management.", "output": '{"needs_sql": true, "needs_visualization": true, "needs_forecast": false, "needs_insight": true, "needs_report": true, "needs_email": true, "chart_type": "auto", "description": "Sales overview email"}'}
    ]
    
    # We will format this for Gemini tuning. 
    # For `genai.create_tuning_job`, we can pass a list of dicts with 'text_input' and 'output'.
    # We will prefix text_input with the system prompt to enforce instruction following.
    
    tuning_data = []
    for ex in examples:
        tuning_data.append({
            "text_input": f"{PLANNER_SYSTEM_PROMPT}\n\nUser Question: {ex['input']}",
            "output": ex['output']
        })
        
    os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)
    out_path = os.path.join(os.path.dirname(__file__), 'data', 'planner_tuning_data.jsonl')
    
    with open(out_path, 'w') as f:
        for item in tuning_data:
            f.write(json.dumps(item) + '\n')
            
    print(f"Generated {len(tuning_data)} examples at {out_path}")
    return out_path

if __name__ == "__main__":
    generate_planner_dataset()
