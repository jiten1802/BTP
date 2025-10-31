import time
import sys
import os
import pandas as pd
from sklearn.metrics import classification_report

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

from agents.interpreter import get_lead_intent
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY_3")
# === Load dummy data from CSV ===
# The CSV should have columns: initial_message, reply, true_intent
df = pd.read_csv(r"C:\Users\shahj\Desktop\Internships_Projects\BTP\data\cold_email_replies_100_intents.csv")

y_true = []
y_pred = []
 # Any string; will fallback if LLM API is not accessible

for idx, row in df.iterrows():
    initial = row["Initial_Message"]
    reply = row["Reply"]
    true_intent = row["Intent"]
    time.sleep(5)
    result = get_lead_intent(initial, reply, GROQ_API_KEY)
    y_true.append(true_intent)
    y_pred.append(result.intent)

print("==== Classification Report ====")
print(classification_report(y_true, y_pred, zero_division=0))