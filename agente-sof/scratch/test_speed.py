import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import google.generativeai as genai
from app.config import get_settings

settings = get_settings()
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

model = genai.GenerativeModel("gemini-2.5-flash")

t0 = time.time()
resp = model.generate_content("Responda em formato JSON: {'status': 'ok'}")
t1 = time.time()

print(f"gemini-2.5-flash levou {t1 - t0:.2f} segundos!")
print(f"Resposta: {resp.text.strip()}")
