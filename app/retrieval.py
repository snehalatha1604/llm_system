import google.generativeai as genai
from openai import OpenAI,AzureOpenAI
import numpy as np
import logging
import re
import time
import itertools
from dotenv import load_dotenv
import os
import pickle
import hashlib
from concurrent.futures import ThreadPoolExecutor
from .embeddings import get_embeddings, build_faiss_index, get_batch_embeddings, save_faiss_index, load_faiss_index
from .prompt_template import TEMPLATE
from .utils import clean_response, contains_api_or_url

load_dotenv()

# PDF cache
pdf_cache = {}
CACHE_DIR = "pdf_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Configuration
openai_client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("OPENAI_API_ENDPOINT1"),
    api_key=os.getenv("OPENAI_API_KEY1")
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Create logs directory
os.makedirs("logs", exist_ok=True)

# Configure logging for api_requests.log
request_logger = logging.getLogger("api_requests")
if not request_logger.handlers:
    request_logger.setLevel(logging.INFO)
    request_handler = logging.FileHandler("logs/api_requests.log")
    request_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    request_logger.addHandler(request_handler)
    request_logger.propagate = False

# Configure logging for api_details.log
detail_logger = logging.getLogger("api_details")
if not detail_logger.handlers:
    detail_logger.setLevel(logging.INFO)
    detail_handler = logging.FileHandler("logs/api_details.log")
    detail_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    detail_logger.addHandler(detail_handler)
    detail_logger.propagate = False

def process_question(q: str, pages: list, index, doc_url: str):
    try:
        print(f"   🔍 Processing question: {q[:50]}...")
        
        print("   📊 Generating question embeddings...")
        q_embeddings = get_embeddings((q,))
        if q_embeddings is None:
            print("   ❌ Failed to generate embeddings")
            return "Unable to process this query"
        
        print("   🔎 Performing vector similarity search...")
        q_embed = q_embeddings[0]
        D, I = index.search(np.array([q_embed]), k=8)
        relevant_chunks = [pages[i] for i in  I[0]]
        print(f"   ✅ Found {len(relevant_chunks)} relevant chunks")
        
        print("   🤖 Checking for interactive instructions...")
        has_instructions = [chunk for chunk in relevant_chunks if contains_api_or_url(chunk)]
        if has_instructions:
            print("   🎯 Interactive instructions detected - Using LangGraph agent")
            from .intractive_agent import reasoning_agent
            import asyncio
            return asyncio.run(reasoning_agent(doc_url, q))
        
        print("   📝 Building prompt for LLM...")
        prompt = TEMPLATE.format(clauses="\n".join(relevant_chunks), question=q)
        token_count = len(prompt.split())
        print(f"   📏 Prompt tokens: {token_count}")
            
        try:
            print("   🚀 Calling Azure OpenAI GPT-4.1-Mini...")
            response = openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            print("   ✅ Received LLM response")
            cleaned_response = clean_response(response.choices[0].message.content)
            print("   🧹 Response cleaned and formatted")
            detail_logger.info(f"Question: {q}")
            # detail_logger.info(f"Gemini - Tokens sent: {token_count}")
            detail_logger.info(f"OPENAI - Response: {cleaned_response}\n")
            return cleaned_response
            
        except Exception as openai_error:
            print("   🚀 OpenAI failed Calling Gemini...")
            detail_logger.warning(f"OpenAI failed Calling Gemini... {openai_error}")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            detail_logger.info(f"Question: {q}")
            detail_logger.info(f"Gemini - Tokens sent: {token_count}")
            print("   ✅ Received Gemini LLM response")
            cleaned_response = clean_response(response.text)
            print("   🧹 Response cleaned and formatted")
            detail_logger.info(f"Gemini - Response: {cleaned_response}\n")
            return cleaned_response
            
    except Exception as e:
        print(f"   ❌ Error processing question: {str(e)}")
        detail_logger.info(f"Question: {q}")
        detail_logger.error(f"Error processing question: {str(e)}")
        return "Unable to process this query"

def get_cache_filename(doc_url, pages):
    """Generate cache filename based on doc_url hash"""
    content_hash = hashlib.md5(doc_url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{content_hash}.pkl")

def get_faiss_filename(doc_url):
    """Generate FAISS index filename based on doc_url hash"""
    content_hash = hashlib.md5(doc_url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{content_hash}.faiss")

def load_from_cache(cache_file, faiss_file):
    """Load pages and FAISS index from cache files"""
    try:
        if not os.path.exists(cache_file) or not os.path.exists(faiss_file):
            return None
            
        # Load pages from pickle
        with open(cache_file, 'rb') as f:
            cached_data = pickle.load(f)
            
        # Load FAISS index directly from disk (much faster)
        index = load_faiss_index(faiss_file)
        if index is not None:
            cached_data['index'] = index
            return cached_data
        return None
    except Exception as e:
        logging.warning(f"Failed to load cache {cache_file}: {e}")
        return None


def save_to_cache(cache_file, faiss_file, pages, index, embeddings=None):
    """Save pages and FAISS index to cache files"""
    try:
        # Save pages to pickle (without embeddings to save space)
        with open(cache_file, 'wb') as f:
            pickle.dump({'pages': pages}, f)
        
        # Save FAISS index directly to disk
        save_faiss_index(index, faiss_file)
    except Exception as e:
        logging.error(f"Failed to save cache: {e}")


def download_and_parse_document(doc_url, file_ext):
    """Download document once and parse based on file type"""
    from .document_parser import parse_pdf, parse_image, parse_pptx, parse_excel, parse_docx
    import requests
    import tempfile
    import os
    
    # Check for unsupported file types
    if file_ext in ['zip', 'bin']:
        print(f"   ❌ Unsupported file type: {file_ext}")
        raise ValueError("The document is not supported")
    
    if file_ext == 'pdf':
        print("   📝 Parsing PDF document directly...")
        return parse_pdf(doc_url)
    
    # Stream download for better performance with large files
    print(f"   ⬇️ Streaming {file_ext.upper()} file...")
    response = requests.get(doc_url, stream=True)
    response.raise_for_status()
    
    content = b''
    for chunk in response.iter_content(chunk_size=8192):
        content += chunk
    print(f"   📋 Downloaded {len(content)} bytes")
    
    with tempfile.NamedTemporaryFile(suffix=f'.{file_ext}', delete=False) as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
            print("   🖼️ Processing image with OCR...")
            return parse_image(tmp_path)
        elif file_ext == 'pptx':
            print("   📊 Processing PowerPoint presentation...")
            return parse_pptx(tmp_path)
        elif file_ext in ['xlsx', 'xls']:
            print("   📈 Processing Excel spreadsheet...")
            return parse_excel(tmp_path)
        elif file_ext == 'docx':
            print("   📄 Processing Word document...")
            return parse_docx(tmp_path)
        else:
            print(f"   ❌ Unsupported file type: {file_ext}")
            raise ValueError("The document is not supported")
    finally:
        os.unlink(tmp_path)

def handle_api_link(doc_url):
    """Handle API links by making requests and extracting data"""
    import requests
    import json
    
    try:
        print("   🌐 Making API request...")
        response = requests.get(doc_url, timeout=30)
        response.raise_for_status()
        print(f"   ✅ API response received: {response.status_code}")
        
        # Try to parse as JSON first
        try:
            print("   📊 Parsing JSON response...")
            data = response.json()
            print("   ✅ JSON parsed successfully")
            return [json.dumps(data, indent=2)]
        except:
            print("   📝 Treating as text response...")
            # If not JSON, return as text
            return [response.text]
    except Exception as e:
        print(f"   ❌ API request failed: {str(e)}")
        raise ValueError(f"Failed to fetch data from API: {str(e)}")

def process_and_answer(pages, questions, doc_url):
    global pdf_cache
    start_time = time.time()
    
    print("\n🔄 Starting document processing pipeline...")
    request_logger.info(f"Received document: {doc_url}")
    request_logger.info(f"Processing {len(questions)} questions")
    detail_logger.info(f"Received document: {doc_url}")

    print("💾 Checking memory cache...")
    cache_key = doc_url
    if cache_key in pdf_cache:
        print("✅ Found in memory cache - Using cached data")
        cached_data = pdf_cache[cache_key]
        pages = cached_data['pages']
        index = cached_data['index']
    else:
        print("💿 Checking disk cache...")
        cache_file = get_cache_filename(doc_url, [])
        faiss_file = get_faiss_filename(doc_url)
        cached_data = load_from_cache(cache_file, faiss_file)
        
        if cached_data:
            print("✅ Found in disk cache - Loading cached embeddings")
            pages = cached_data['pages']
            index = cached_data['index']
            pdf_cache[cache_key] = cached_data
        else:
            print("🆕 No cache found - Processing new document")
            # Check if it's an API link (no file extension or specific API patterns)
            url_path = doc_url.split('/')[-1].split('?')[0]
            if '.' in url_path:
                file_ext = url_path.lower().split('.')[-1]
                print(f"📄 Detected file type: {file_ext}")
                request_logger.info(f"File {file_ext}")
                print("⬇️ Downloading and parsing document...")
                pages = download_and_parse_document(doc_url, file_ext)  # Will properly block ZIP/BIN
            else:
                print("🌐 No file extension detected - Treating as API endpoint")
                print("📡 Fetching data from API...")
                pages = handle_api_link(doc_url)
            
            if not pages or len(" ".join(pages)) < 10:
                raise ValueError("The document is not supported")
            
            print(f"📚 Extracted {len(pages)} text chunks")
            
            # Filter out empty or very short chunks
            valid_pages = [page.strip() for page in pages if page and page.strip() and len(page.strip()) > 10]
            print(f"🧹 Filtered to {len(valid_pages)} valid chunks")
            
            if not valid_pages:
                raise ValueError("No valid text content found in document")
            
            print("🧠 Generating document embeddings in batches...")
            
            # Use batch processing for better performance
            if len(valid_pages) > 10:
                chunk_embeddings = get_batch_embeddings(valid_pages, batch_size=16)
            else:
                chunk_embeddings = get_embeddings(tuple(valid_pages))
                
            # Update pages to use only valid chunks
            pages = valid_pages
                
            if chunk_embeddings is None:
                raise ValueError("Failed to generate embeddings")
            
            print("🔍 Building FAISS vector index...")
            index = build_faiss_index(chunk_embeddings)
            
            print("💾 Saving to cache for future use...")
            cached_data = {'pages': pages, 'index': index}
            save_to_cache(cache_file, faiss_file, pages, index)
            pdf_cache[cache_key] = cached_data
    
    print(f"\n🎯 Processing {len(questions)} questions in parallel...")
    
    with ThreadPoolExecutor(max_workers=min(len(questions), 16)) as executor:
        futures = [executor.submit(process_question, q, pages, index, doc_url) for q in questions]
        answers = [future.result() for future in futures]
    
    elapsed_time = time.time() - start_time
    print(f"\n✅ All questions processed in {elapsed_time:.2f}s")
    
    return answers
            