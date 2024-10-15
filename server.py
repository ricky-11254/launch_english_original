import language_tool_python
import httpx
import whisper
import time
import requests
from fastapi import FastAPI, UploadFile, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pyngrok import ngrok
from sentence_transformers import SentenceTransformer, util
import uvicorn
import os

# Initialize FastAPI app
app = FastAPI()
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates directory
templates = Jinja2Templates(directory="templates")

# Load our models
model = whisper.load_model("base")
nlp_model = SentenceTransformer("sentence-transformers/roberta-base-nli-stsb-mean-tokens")

#Our template
sentence_template = "A person is boarding a train."

# File directory settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static/audio/")
timestr = time.strftime("%Y%m%d-%H%M%S")

# Ensure the upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/toeic_speaking")
async def toeic_speaking(request: Request):
    return templates.TemplateResponse("toeic_speaking.html", {"request": request})

@app.get("/cathoven")
async def cathoven(request: Request):
    return templates.TemplateResponse("cathoven.html", {"request": request})

@app.get("/")
async def read_root(request: Request):
    with open('public_url.txt', 'r') as f:
        server_url = f.read()
    return templates.TemplateResponse("cathoven.html", {"request": request, "server_url": server_url})

@app.post("/upload")
async def upload_file(file: UploadFile):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid audio file type")
    
    file_data = await file.read()
    new_filename = f"{os.path.splitext(file.filename)[0]}_{timestr}.wav"
    save_file_path = os.path.join(UPLOAD_DIR, new_filename)
    
    with open(save_file_path, "wb") as f:
        f.write(file_data)
    
    result = model.transcribe(save_file_path)
    print(result)

    # Use LanguageTool to check and correct the transcription
    my_tool = language_tool_python.LanguageTool('en-US', config={'cacheSize': 1000, 'pipelineCaching': True})
    my_text = my_tool.correct(result["text"])

    if my_text.lower() == result["text"].lower():
        correct_text = f'You said "{result["text"]}" and it is correct.'
    else:
        correct_text = f'The correct way to say that: "{my_text}"'

    # Step 1: Keyword matching with sentence template
    template_keywords = ["person", "boarding", "train"]
    transcription_words = result["text"].lower().split()
    matched_keywords = [word for word in template_keywords if word in transcription_words]
    keyword_score = len(matched_keywords) / len(template_keywords) * 100

    #Step 2: Semantic similarity with the template sentence
    # Get embeddings for both the transcription and the template
    embedding_1 = nlp_model.encode(result["text"], convert_to_tensor=True)
    embedding_2 = nlp_model.encode(sentence_template, convert_to_tensor=True)

    #Compute cosine similarity between the transcription and the sentence template 
    semantic_score = util.pytorch_cos_sim(embedding_1, embedding_2).item() * 100  # RoBERTa similarity score

    # Final Score (weighted combination of keyword matching and semantic similarity)
    final_score = (0.5 * keyword_score) + (0.5 * semantic_score)

    original_words = result["text"].lower().split()
    corrected_words = my_text.lower().split()
    correct_word_count = sum(1 for o, c in zip(original_words, corrected_words) if o == c)
    score_percentage = (correct_word_count / len(corrected_words)) * 100 if corrected_words else 0

    return JSONResponse(content={
        "transcription": result["text"],
        "correction": correct_text,
        "score_percentage": score_percentage,
        "keyword_score": keyword_score,
        "semantic_score": semantic_score,
        "final_score": final_score,
    })

class TextInput(BaseModel):
    text: str

@app.post("/cathoven")
async def cathoven(input: TextInput):
    text = input.text
    print(text)
    url = "https://enterpriseapi.cathoven.com/cefr/process_text"
    payload = {
        "client_id": "your_client_id",
        "client_secret": "your_client_secret",
        "text": text, 
        "v": 2
    }
    headers = {
        'Content-Type': 'application/json'
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload) 

    if response.status_code == 200:
        try:
            answer = response.json()
            print(answer)
        except ValueError:
            raise HTTPException(status_code=500, detail="Invalid JSON response from Cathoven API")
    else:
        return JSONResponse(content={"failed": f"API request failed with status code {response.status_code}"})

    
    return JSONResponse(content={
        "answer": answer,
    })

# Start the FastAPI server
if __name__ == "__main__":
    public_url = ngrok.connect(8002).public_url
    with open('public_url.txt', 'w') as f:
        f.write(public_url)
    print(f"Public URL: {public_url}")
    uvicorn.run("server:app", host="127.0.0.1", port=8002, reload=True)

