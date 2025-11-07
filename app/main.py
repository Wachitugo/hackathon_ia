from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import random
import json
import re
from typing import Any, Dict

# importar el orquestador de agentes
try:
	from src.agents.agents_factory import run_agent_flow
except Exception:
	# fallback si se ejecuta desde diferente cwd
	try:
		from agents.agents_factory import run_agent_flow
	except Exception:
		run_agent_flow = None


# Rutas de directorios relativas a este archivo (app/main.py)
BASE_DIR = Path(__file__).resolve().parent  # app/
TEMPLATES_DIR = BASE_DIR.parent / "templates"  # ../templates
STATIC_DIR = BASE_DIR.parent / "static"  # ../static


app = FastAPI(title="hackathon_ia")


# Montar archivos estáticos si existen
if STATIC_DIR.exists():
	app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Configurar Jinja2 para servir plantillas desde ../templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
	"""Devuelve `index.html` tal cual (archivo estático) para evitar que Jinja2 interpete sintaxis de React/JSX."""
	index_path = TEMPLATES_DIR / "index.html"
	if not index_path.exists():
		return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)
	return FileResponse(path=str(index_path), media_type="text/html")


@app.get("/ping")
async def ping():
	return {"status": "ok"}


# Modelo para las peticiones del chat
class ChatRequest(BaseModel):
	message: str


# Modelo para las respuestas del chat
class ChatResponse(BaseModel):
	response: str


# Modelo para las peticiones del chat
class ChatRequest(BaseModel):
	message: str


# Modelo para las respuestas del chat
class ChatResponse(BaseModel):
	response: str


def format_response_to_html(text: str) -> str:
    """
    Convierte texto con formato simple o sin formato a HTML estructurado.
    """
    html = text
    
    # --- 1. Búsqueda de formato explícito --- 
    has_explicit_format = False
    if html.startswith('[Title: ') or "**" in html:
        has_explicit_format = True

    if has_explicit_format:
        if html.startswith('[Title: '):
            title_end = html.find(']')
            if title_end != -1:
                title = html[8:title_end]
                html = html[title_end+1:].strip()
                html = f"<h3>{title}</h3>{html}"

        html = html.replace("**Introducción**", "<h4>Introducción</h4>")
        html = html.replace("**Tipos de Diabetes**", "<h4>Tipos de Diabetes</h4>")
        html = html.replace("**Complicaciones**", "<h4>Complicaciones</h4>")
        html = html.replace("**Diagnóstico**", "<h4>Diagnóstico</h4>")
        html = html.replace("**Prevención y Control**", "<h4>Prevención y Control</h4>")
        
        parts = html.split("<h4>")
        processed_html = ""
        if parts:
            first_part = parts[0]
            h3_end_index = first_part.find("</h3>")
            if h3_end_index != -1:
                processed_html += first_part[:h3_end_index+5]
                remaining_text = first_part[h3_end_index+5:].strip()
                if remaining_text:
                    processed_html += f"<p>{remaining_text}</p>"
            elif first_part.strip():
                processed_html += f"<p>{first_part.strip()}</p>"

            for part in parts[1:]:
                h4_end_index = part.find("</h4>")
                if h4_end_index != -1:
                    title = part[:h4_end_index]
                    content = part[h4_end_index+5:].strip()
                    processed_html += f"<h4>{title}</h4>"
                    if content:
                        processed_html += f"<p>{content}</p>"
        return processed_html

    # --- 2. Búsqueda de palabras clave si no hay formato explícito ---
    keywords = ["Introducción", "Tipos de Diabetes", "Síntomas", "Diagnóstico", "Complicaciones", "Tratamiento"]
    temp_html = html
    found_keywords = False

    # Ordenar keywords por longitud para evitar matching parcial (ej. "Tipos" vs "Tipos de Diabetes")
    keywords.sort(key=len, reverse=True)

    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, temp_html, re.IGNORECASE):
            found_keywords = True
            temp_html = re.sub(pattern, f"---section---{keyword}", temp_html, count=1, flags=re.IGNORECASE)

    if found_keywords:
        processed_html = "<h3>Información sobre Diabetes</h3>"
        sections = temp_html.split('---section---')
        
        if sections[0].strip():
            processed_html += f"<p>{sections[0].strip()}</p>"
            
        for section_content in sections[1:]:
            section_content = section_content.strip()
            found_title = None
            
            for keyword in keywords:
                if section_content.lower().startswith(keyword.lower()):
                    actual_title = section_content[:len(keyword)]
                    remaining_content = section_content[len(keyword):].strip()
                    
                    processed_html += f"<h4>{actual_title}</h4>"
                    if remaining_content:
                        processed_html += f"<p>{remaining_content}</p>"
                    found_title = True
                    break
            
            if not found_title and section_content:
                processed_html += f"<p>{section_content}</p>"
        return processed_html

    # --- 3. Fallback: sin formato y sin palabras clave ---
    return f"<h3>Información</h3><p>{text}</p>"


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint de chatbot que utiliza el flujo de agentes para generar respuestas.
    """
    if run_agent_flow is None:
        return ChatResponse(response="Error: El flujo de agentes no está disponible.")

    try:
        out = run_agent_flow(request.message)
        raw_response = out.get('final', 'Lo siento, no pude generar una respuesta.')
        formatted_response = format_response_to_html(raw_response)
        return ChatResponse(response=formatted_response)
    except Exception as e:
        return ChatResponse(response=f"Error: {e}")


from api import coach

app.include_router(coach.router, prefix="/api/coach", tags=["coach"])


if __name__ == "__main__":
	# Permite ejecutar `python app/main.py` para desarrollo local
	uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
