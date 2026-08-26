import os
os.environ['SANDBOX_MODE'] = '1'
from engine.briefing.data import gather_all, narrator_payload
from engine.briefing.narrator import generate_narrative

data = gather_all()
payload = narrator_payload(*data)
print("Payload tax data:", payload.get("tax_harvesting"))

# Call LLM
result = generate_narrative(payload, model="qwen2.5:3b") # use small model for speed
print("\n--- Narrative ---")
print(result["narrative"])
print("\n--- Tax Advice ---")
print(result["tax_advice"])
