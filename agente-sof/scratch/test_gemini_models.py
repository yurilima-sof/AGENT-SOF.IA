import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import google.generativeai as genai
from app.config import get_settings

settings = get_settings()
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

models_to_test = [
    "gemini-flash-latest",
    "gemini-1.5-flash-latest",
    "models/gemini-1.5-flash-latest",
    "gemini-2.0-flash",
    "gemini-2.5-flash"
]

print("=== TESTANDO MODELOS GEMINI DISPONIVEIS ===")
for m in models_to_test:
    try:
        model = genai.GenerativeModel(m)
        resp = model.generate_content("Diga ola em uma palavra")
        print(f"OK - Modelo '{m}': FUNCIONOU! Resposta: {resp.text.strip()}")
    except Exception as e:
        print(f"ERRO - Modelo '{m}': {e}")
