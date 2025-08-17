from fastapi import FastAPI, HTTPException, Depends, Header, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .embeddings import get_embeddings
from .retrieval import process_and_answer
import logging
import warnings
import json
import time
import os
from datetime import datetime
import pytz
import asyncio

# Suppress various library warnings
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Create logs directory
os.makedirs("logs", exist_ok=True)

logging.basicConfig(level=logging.INFO, filename="logs/usage.log", format="%(asctime)s - %(message)s")

# JSON request logger
json_logger = logging.getLogger("json_requests")
json_logger.setLevel(logging.INFO)
json_handler = logging.FileHandler("logs/requests.json", mode='a')
json_handler.setFormatter(logging.Formatter('%(message)s'))
json_logger.addHandler(json_handler)

app = FastAPI(title="LLM-Powered Query-Retrieval System")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# WebSocket connections
connected_clients = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        connected_clients.discard(websocket)

@app.get("/api/logs")
def get_logs():
    try:
        with open("logs/requests.json", "r") as f:
            content = f.read().strip()
            logs = []
            
            # Use regex to find JSON objects
            import re
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, content, re.DOTALL)
            
            for match in matches:
                try:
                    logs.append(json.loads(match))
                except json.JSONDecodeError:
                    continue
            
            return {"logs": logs[-20:]}  # Return last 20 requests
    except FileNotFoundError:
        return {"logs": []}
    except Exception as e:
        return {"logs": []}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Capture body for POST requests before processing
    body_content = None
    if request.method == "POST":
        body = await request.body()
        body_content = body.decode() if body else None
    
    # Process request
    response = await call_next(request)
    
    # Only log POST requests
    if request.method == "POST":
        request_data = {
            "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": body_content,
            "client_ip": request.client.host,
            "status_code": response.status_code,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "response_body": response_data_store.get('latest')
        }
        
        # Log as JSON
        json_logger.info(json.dumps(request_data))
        
        # Send to WebSocket clients
        if connected_clients:
            message = json.dumps({"type": "new_request", "data": request_data})
            for client in connected_clients.copy():
                try:
                    asyncio.create_task(client.send_text(message))
                except:
                    connected_clients.discard(client)
    
    return response

@app.on_event("startup")
def warmup():
    print("\n" + "=" * 60)
    print("🚀 BAJAJ HACKRX - LLM Document Query System")
    print("=" * 60)
    print(f"🔍 Starting up at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')}...")
    
    # Check API keys
    print("🔑 Checking API keys...")
    openai_key = os.getenv('OPENAI_API_KEY')
    nvidia_key = os.getenv('NVIDIA_API_KEY')
    gemini_keys = [os.getenv(f'GEMINI_API_KEY{i}') for i in range(1, 6)]
    
    print(f"   OpenAI: {'✅' if openai_key else '❌'}")
    print(f"   NVIDIA: {'✅' if nvidia_key else '❌'}")
    print(f"   Gemini: {'✅' if any(gemini_keys) else '❌'} ({sum(1 for k in gemini_keys if k)} keys)")
    
    get_embeddings(("warmup",))  # Load model
    print(f"✅ System ready at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')} - Waiting for requests...")
    print("📡 Monitoring API endpoint: /api/v1/hackrx/run")
    print("=" * 60)

VALID_TOKEN = "6474bf54ce9dc3d156827448363ba8f461b0366cb1e1d8e41aae7e6157a30ce0"

def verify_token(authorization: str = Header()):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split(" ")[1]
    if token != VALID_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

class QueryRequest(BaseModel):
    documents: str
    questions: list[str]

def print_request_info(req: QueryRequest):
    print("\n" + "=" * 60)
    print(f"⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')}")
    print("📡 New API request received!")
    print(f"📄 Document: {req.documents}")
    print(f"📊 Questions received: {len(req.questions)}")
    print(f"🔄 Processing {len(req.questions)} question(s)...")

def print_completion_info(num_questions: int, elapsed_time: float):
    print(f"✅ All {num_questions} questions answered in {elapsed_time:.1f}s")
    print("=" * 60)



# Store for response logging
response_data_store = {}

@app.post("/api/v1/hackrx/run")
def run_query(req: QueryRequest, token: str = Depends(verify_token)):
    print_request_info(req)
    start_time = time.time()
    
    try:
        answers = process_and_answer(None, req.questions, req.documents)
        elapsed_time = time.time() - start_time
        print_completion_info(len(req.questions), elapsed_time)
        response_body = {"answers": answers}
        
        # Store response for middleware
        response_data_store['latest'] = json.dumps(response_body)
        
        return response_body
    except Exception as e:
        elapsed_time = time.time() - start_time
        logging.error(f"Failed to process request: {e}")
        print(f"❌ Request failed after {elapsed_time:.1f}s: {e}")
        print("=" * 60)
        error_response = {"answers": ["The document is not supported"] * len(req.questions)}
        
        # Store error response for middleware
        response_data_store['latest'] = json.dumps(error_response)
        
        return error_response
