import os
import sys
import time
import pandas as pd
import yaml
from tqdm import tqdm
from dotenv import load_dotenv
import logging
from typing import Dict, Any, List
from contextlib import contextmanager

# --- Add project root to Python path ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# --- Sklearn and App-specific Imports ---
from sklearn.metrics import precision_recall_fscore_support, mean_absolute_error, accuracy_score
from app.models.state import AgenticState, Lead

# --- Import the ENTIRE prospector module ---
# This is crucial for monkey patching
import app.agents.prospector_llm as prospector_module

# --- Setup ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- 1. Monkey Patching Helper ---

@contextmanager
def patch_prospector_model(model_name: str):
    """
    A context manager to temporarily replace the model used by the Prospector agent.
    This is the core of the "no changes" testing approach.
    """
    # Store the original function to restore it later
    original_create_llm_func = prospector_module.create_llm_with_key
    
    # Define a new function with the desired model name baked in
    def new_create_llm_with_key(api_key: str, batch_mode: bool = False):
        from langchain_groq import ChatGroq
        from app.agents.prospector_llm import BatchLeadScore, LeadScore

        # This is where we override the model name
        llm = ChatGroq(model=model_name, temperature=0.7, groq_api_key=api_key)
        return llm.with_structured_output(BatchLeadScore if batch_mode else LeadScore)

    # The "monkey patch": replace the agent's function with our new one
    prospector_module.create_llm_with_key = new_create_llm_with_key
    
    try:
        yield
    finally:
        # The magic: no matter what happens, restore the original function
        prospector_module.create_llm_with_key = original_create_llm_func


# --- 2. Data Loading and Rule-Based Baseline ---

def load_golden_dataset(filepath: str) -> pd.DataFrame:
    """Loads the ground truth dataset from a CSV file."""
    return pd.read_csv(filepath)

def load_icp_config_for_baseline() -> Dict[str, Any]:
    config_path = os.path.join(PROJECT_ROOT, "configs", "icp.yaml")
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def score_lead_rule_based(lead_data: Dict, icp: Dict) -> Dict:
    """(Group C) A simple, non-AI baseline."""
    # ... (This function is identical to the one in the previous script)
    score = icp['scoring_weights']['base_score']
    is_excluded = False
    if lead_data.get('industry') in icp['firmographics']['target_industries']: score += icp['scoring_weights']['industry_match']
    emp_count = lead_data.get('employee_count', 0)
    if icp['firmographics']['employee_count']['min'] <= emp_count <= icp['firmographics']['employee_count']['max']: score += icp['scoring_weights']['employee_count_within_range']
    if lead_data.get('location') in icp['firmographics']['locations']: score += icp['scoring_weights']['location_match']
    job_title = lead_data.get('job_title', '').lower()
    if any(title.lower() in job_title for title in icp['persona']['job_titles']): score += icp['scoring_weights']['job_title_match']
    if any(title.lower() in job_title for title in icp['persona']['excluded_titles']): score += icp['scoring_weights']['is_excluded_title']; is_excluded = True
    score = max(0, min(100, score))
    status = "NEEDS_REVIEW"
    if score >= 50 and not is_excluded: status = "QUALIFIED"
    elif score < 30 or is_excluded: status = "NOT_QUALIFIED"
    return {"lead_score": score, "qualification_status": status}

# --- 3. Metrics Calculation (Same as before) ---
def calculate_and_print_metrics(results, ground_truth, model_name, total_time):
    print(f"\n--- Results for Model: {model_name} ---")
    
    # The merge is correct, but we need to reference the columns properly
    merged_df = ground_truth.merge(results, left_on='email', right_on='email', suffixes=('_true', '_pred'))
    if merged_df.empty:
        print("No results to compare.")
        return

    # --- THIS IS THE FIX ---
    # The original ground truth column does not get a suffix if the name is unique.
    # We reference it by its original name.
    y_true_status = merged_df['qualification_status'] # Corrected: from 'qualification_status_true'
    y_pred_status = merged_df['qualification_status_pred']
    y_true_score = merged_df['score'] # Corrected: from 'score_true'
    y_pred_score = merged_df['score_pred']
    # --- END OF FIX ---
    
    # The rest of the calculation is the same
    accuracy = accuracy_score(y_true_status, y_pred_status)
    precision, recall, f1, _ = precision_recall_fscore_support(y_true_status, y_pred_status, average='weighted', zero_division=0)
    mae = mean_absolute_error(y_true_score, y_pred_score)
    throughput = len(ground_truth) / total_time if total_time > 0 else 0
    
    print("\nClassification Performance:")
    print(f"  Accuracy: {accuracy:.2%}")
    print(f"  Precision (weighted): {precision:.2f}")
    print(f"  Recall (weighted): {recall:.2f}")
    print(f"  F1-Score (weighted): {f1:.2f}")
    print("\nScoring Performance:")
    print(f"  Mean Absolute Error (MAE): {mae:.2f} points")
    print("\nPerformance & Throughput:")
    print(f"  Total Execution Time: {total_time:.2f} seconds")
    print(f"  Throughput: {throughput:.2f} leads/second")

# --- Main Execution Block ---
if __name__ == "__main__":
    MODELS_TO_TEST = {
        "Rule-Based Baseline": None,
        "Llama-3.1-8B (Fast)": "llama-3.1-8b-instant",
        "Llama-3.1-70B (Powerful)": "llama-3.3-70b-versatile",
    }
    DATASET_PATH = os.path.join(PROJECT_ROOT, "data", "qualified_leads_data.csv")

    golden_df = load_golden_dataset(DATASET_PATH)
    all_results = {}

    for model_display_name, model_api_name in MODELS_TO_TEST.items():
        print(f"\n>>> Running experiment for: {model_display_name} <<<")
        
        initial_leads = [
            Lead(lead_id=str(idx), raw_data=row.to_dict(), status="new")
            for idx, row in golden_df.iterrows()
        ]
        initial_state = AgenticState(lead=initial_leads)
        
        start_time = time.time()
        
        if model_api_name is None: # Rule-based baseline
            # --- THIS IS THE FIXED SECTION ---
            predictions = [score_lead_rule_based(lead.raw_data, load_icp_config_for_baseline()) for lead in initial_leads]
            
            # Now, correctly update the Lead objects based on our model
            for i, lead in enumerate(initial_leads):
                prediction = predictions[i]
                lead.score = prediction['lead_score']
                # Correctly set the 'qualified_lead' boolean field
                lead.qualified_lead = (prediction['qualification_status'] == 'QUALIFIED')
            # --- END OF FIX ---
            final_state = initial_state
        else: # LLM-based agent
            with patch_prospector_model(model_api_name):
                final_state = prospector_module.Prospector(initial_state)
        
        total_time = time.time() - start_time
        
        run_results = []
        for lead in final_state.lead:
            email = lead.raw_data.get('email')
            
            # --- THIS IS THE SECOND PART OF THE FIX ---
            # Now we correctly infer the status from the boolean 'qualified_lead'
            # and the raw 'status' field for all cases.
            status_pred = "NEEDS_REVIEW" # Default
            if lead.status == 'failed':
                status_pred = "NOT_QUALIFIED"
            elif lead.qualified_lead:
                status_pred = "QUALIFIED"
            # We need a rule to determine NOT_QUALIFIED for non-failed leads.
            # Let's align with the Prospector's prompt logic.
            elif lead.score is not None and lead.score < 30:
                 status_pred = "NOT_QUALIFIED"
            # We also need to check for excluded titles, but the baseline doesn't return that.
            # For the LLM agent, it correctly sets the status. For our baseline, this is an acceptable simplification.

            # Special handling for our baseline, as it doesn't set the lead's main `status` field.
            if model_api_name is None:
                # Find the corresponding prediction we made earlier
                rule_based_prediction = score_lead_rule_based(lead.raw_data, load_icp_config_for_baseline())
                status_pred = rule_based_prediction['qualification_status']

            run_results.append({
                "email": email,
                "score_pred": lead.score,
                "qualification_status_pred": status_pred
            })
            
        all_results[model_display_name] = (pd.DataFrame(run_results), total_time)

    # --- Reporting (No changes needed in the reporting part) ---
    print("\n" + "="*50)
    print("      PROSPECTOR AGENT INTEGRATION TEST REPORT")
    print("="*50)

    for model_name, (results_df, total_time) in all_results.items():
        calculate_and_print_metrics(results_df, golden_df, model_name, total_time)