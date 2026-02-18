import os
import base64
import time
import random
from openai import OpenAI
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
from django.conf import settings

def generate_ai_response(messages, model_name, temperature=0.5, response_format=None):
    """
    Fonction unifiée pour appeler l'IA (OpenAI ou Gemini).
    Retourne le texte de la réponse.
    """
    if "gemini" in model_name.lower():
        return _call_gemini(messages, model_name, temperature, response_format)
    else:
        return _call_openai(messages, model_name, temperature, response_format)

def _call_openai(messages, model, temperature, response_format):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format=response_format
    )
    return completion.choices[0].message.content

def _call_gemini(messages, model, temperature, response_format):
    if genai is None:
        raise ImportError("La librairie 'google-genai' n'est pas installée.")
        
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    system_instruction = None
    contents = []
    
    # Conversion du format OpenAI (messages) vers Gemini (contents + system_instruction) avec le nouveau SDK
    for msg in messages:
        if msg['role'] == 'system':
            system_instruction = msg['content']
        else:
            role = 'model' if msg['role'] == 'assistant' else 'user'
            parts = []
            
            content = msg.get('content')
            if isinstance(content, str):
                parts.append(types.Part.from_text(text=content))
            elif isinstance(content, list):
                for item in content:
                    if item.get('type') == 'text':
                        parts.append(types.Part.from_text(text=item.get('text')))
                    elif item.get('type') == 'image_url':
                        # Gestion des images (base64 data URI)
                        url = item.get('image_url', {}).get('url', '')
                        if url.startswith('data:image'):
                            try:
                                header, encoded = url.split(",", 1)
                                mime_type = header.split(":")[1].split(";")[0]
                                data = base64.b64decode(encoded)
                                parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))
                            except Exception as e:
                                print(f"Erreur décodage image Gemini: {e}")
            
            if parts:
                contents.append(types.Content(role=role, parts=parts))
    
    # Configuration de la génération
    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction
    )
    
    if response_format and response_format.get("type") == "json_object":
        config.response_mime_type = "application/json"
    
    # Mécanisme de retry pour gérer les erreurs de quota (429)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Quota exceeded" in error_str or "ResourceExhausted" in error_str:
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) * 2 + random.uniform(0, 1)
                    print(f"DEBUG: [Gemini] Quota dépassé. Nouvelle tentative dans {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                    continue
            raise e