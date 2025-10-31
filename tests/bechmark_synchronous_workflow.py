# tests/benchmark_synchronous_workflow.py

import os
import sys
import time
import requests
import pandas as pd
from tqdm import tqdm

# --- Add project root to Python path ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"  # The address of your running FastAPI server
LEADS_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "leads.csv")

def check_server_status():
    """Checks if the FastAPI server is running."""
    try:
        response = requests.get(API_BASE_URL)
        if response.status_code == 200:
            print("✅ FastAPI server is running.")
            return True
        else:
            print(f"❌ Server responded with status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ FastAPI server is not running. Please start it with 'python -m app.run_server'.")
        return False

def run_agent(agent_name: str) -> dict:
    """Makes a POST request to run a specific agent and returns the JSON response."""
    url = f"{API_BASE_URL}/{agent_name}/run"
    print(f"\n--- 🚀 Triggering {agent_name.capitalize()} Agent ---")
    try:
        response = requests.post(url)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"🔥 Error running {agent_name} agent: {e}")
        return {}

def get_current_state() -> dict:
    """Fetches the current global state from the API."""
    url = f"{API_BASE_URL}/state"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"🔥 Error fetching state: {e}")
        return {}

if __name__ == "__main__":
    if not check_server_status():
        sys.exit(1)

    # --- Load Dataset to get the total number of leads ---
    try:
        leads_df = pd.read_csv(LEADS_DATA_PATH)
        total_leads_in_dataset = len(leads_df)
        print(f"Found {total_leads_in_dataset} leads in the dataset to process.")
    except FileNotFoundError:
        print(f"❌ Leads data file not found at: {LEADS_DATA_PATH}")
        sys.exit(1)
        
    print("\n" + "="*50)
    print("  STARTING SYNCHRONOUS WORKFLOW BENCHMARK")
    print("="*50)

    # Record the overall start time
    workflow_start_time = time.time()
    
    # === STEP 1: Run Prospector ===
    prospector_start_time = time.time()
    prospector_result = run_agent("prospector")
    prospector_end_time = time.time()
    prospector_duration = prospector_end_time - prospector_start_time
    
    # === STEP 2: Run Strategist ===
    strategist_start_time = time.time()
    strategist_result = run_agent("strategist")
    strategist_end_time = time.time()
    strategist_duration = strategist_end_time - strategist_start_time

    # === STEP 3: Run Communicator ===
    communicator_start_time = time.time()
    communicator_result = run_agent("communicator")
    communicator_end_time = time.time()
    communicator_duration = communicator_end_time - communicator_start_time

    # Record the overall end time
    workflow_end_time = time.time()
    total_workflow_duration = workflow_end_time - workflow_start_time
    
    # === STEP 4: Fetch Final State and Report Metrics ===
    final_state = get_current_state()
    performance_metrics = final_state.get("performance_metrics", {})
    
    # Extract key metrics
    processed_leads = performance_metrics.get("processed_leads", 0)
    qualified_leads = performance_metrics.get("qualified_leads", 0)
    messages_generated = performance_metrics.get("messages_generated", 0)
    emails_sent = performance_metrics.get("emails_sent", 0)
    
    # Calculate throughput
    throughput = processed_leads / total_workflow_duration if total_workflow_duration > 0 else 0

    print("\n" + "="*50)
    print("      SYNCHRONOUS WORKFLOW BENCHMARK REPORT")
    print("="*50)
    
    print("\n📊 Overall Performance:")
    print(f"  - Total Leads Processed: {processed_leads} / {total_leads_in_dataset}")
    print(f"  - Total Time Elapsed: {total_workflow_duration:.2f} seconds")
    print(f"  - Overall Throughput: {throughput:.2f} leads/second")

    print("\n⏱️ Agent Execution Times:")
    print(f"  - Prospector:   {prospector_duration:.2f} seconds")
    print(f"  - Strategist:   {strategist_duration:.2f} seconds")
    print(f"  - Communicator: {communicator_duration:.2f} seconds")

    print("\n📈 Funnel Metrics:")
    print(f"  - Leads Scored: {processed_leads}")
    print(f"  - Leads Qualified: {qualified_leads}")
    print(f"  - Personalized Messages Generated: {messages_generated}")
    print(f"  - Emails Sent: {emails_sent}")
    print("\n" + "="*50)