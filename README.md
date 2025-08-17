# LLM-Powered Document Query System

A FastAPI-based system that processes various document formats and answers questions using advanced language models and vector embeddings.

## Features

- **Multi-format Document Support**: PDF, DOCX, PPTX, Excel, Images (OCR), API endpoints
- **Vector Search**: FAISS-powered semantic search with NVIDIA embeddings
- **Multiple LLM Backends**: Azure OpenAI GPT-5-Nano, Google Gemini, with intelligent fallback
- **Interactive Agent**: LangGraph-powered agent for complex multi-step queries
- **Real-time Monitoring**: WebSocket-enabled request monitoring dashboard
- **Caching System**: Memory and disk caching for improved performance
- **Batch Processing**: Parallel question processing with ThreadPoolExecutor

## Architecture

### System Workflow

```mermaid
flowchart TD
    A[Client Request] --> B[FastAPI Server]
    B --> C{Document Type?}
    
    C -->|PDF| D[PDF Parser]
    C -->|DOCX| E[Word Parser]
    C -->|PPTX| F[PowerPoint Parser]
    C -->|Excel| G[Excel Parser]
    C -->|Image| H[OCR Parser]
    C -->|API| I[Web Scraper]
    
    D --> J[Text Extraction]
    E --> J
    F --> J
    G --> J
    H --> J
    I --> J
    
    J --> K{Cache Check}
    K -->|Hit| L[Load from Cache]
    K -->|Miss| M[Generate Embeddings]
    
    M --> N[NVIDIA LLaMA-3.2]
    N --> O[FAISS Index]
    O --> P[Save to Cache]
    
    L --> Q[Vector Search]
    P --> Q
    
    Q --> R{Interactive?}
    R -->|Yes| S[LangGraph Agent]
    R -->|No| T[Direct LLM]
    
    S --> U[Groq API]
    T --> V{Primary LLM}
    V -->|Available| W[Azure OpenAI GPT-5]
    V -->|Fallback| X[Google Gemini]
    
    U --> Y[Response]
    W --> Y
    X --> Y
    
    Y --> Z[Client Response]
    
    B --> AA[WebSocket Monitor]
    AA --> BB[React Dashboard]
```

### Project Structure

```
├── app/                    # Core application
│   ├── main.py            # FastAPI server and endpoints
│   ├── document_parser.py # Multi-format document parsing
│   ├── embeddings.py      # NVIDIA embeddings and FAISS indexing
│   ├── retrieval.py       # Vector search and LLM integration
│   ├── intractive_agent.py # LangGraph reasoning agent
│   ├── prompt_template.py # LLM prompt templates
│   └── utils.py           # Utility functions
├── web/                   # React monitoring dashboard
├── test/                  # Test files
└── run_server.py         # Server launcher
```

## Setup

### Prerequisites

- Python 3.8+
- Node.js 16+ (for web dashboard)
- Tesseract OCR (for image processing)

### Installation

1. **Clone and setup Python environment:**
```bash
git clone <repository-url>
cd llm_system
pip install -r requirements.txt
```

2. **Install Tesseract OCR:**
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

3. **Setup web dashboard:**
```bash
cd web
npm install
```

4. **Configure environment variables:**
```bash
# Create .env file with your API keys
NVIDIA_API_KEY=your_nvidia_api_key
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY1=your_gemini_api_key_1
GEMINI_API_KEY2=your_gemini_api_key_2
GEMINI_API_KEY3=your_gemini_api_key_3
GROQ_API_KEY=your_groq_api_key
```

## Usage

### Start the Server

```bash
# Development mode with auto-reload
python run_server.py

# Or directly with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start Web Dashboard

```bash
cd web
npm start
```

### API Endpoints

#### Main Query Endpoint
```http
POST /api/v1/hackrx/run
Authorization: Bearer 6474bf54ce9dc3d156827448363ba8f461b0366cb1e1d8e41aae7e6157a30ce0
Content-Type: application/json

{
  "documents": "https://example.com/document.pdf",
  "questions": [
    "What is the main topic of this document?",
    "Summarize the key findings."
  ]
}
```

#### Monitoring Endpoints
- `GET /api/logs` - Retrieve request logs
- `WebSocket /ws` - Real-time request monitoring

## Supported Document Types

| Format | Extensions | Features |
|--------|------------|----------|
| PDF | `.pdf` | Text extraction, URL support |
| Word | `.docx` | Full document parsing |
| PowerPoint | `.pptx` | Text + OCR for images |
| Excel | `.xlsx`, `.xls` | Multi-sheet processing |
| Images | `.jpg`, `.png`, `.gif`, etc. | OCR with Tesseract |
| API | No extension | JSON/HTML content |

## Key Components

### Document Processing Pipeline
1. **Format Detection**: Automatic file type identification
2. **Content Extraction**: Format-specific parsing with OCR support
3. **Text Chunking**: Intelligent content segmentation
4. **Embedding Generation**: NVIDIA LLaMA-3.2 embeddings
5. **Vector Indexing**: FAISS similarity search

### LLM Integration
- **Primary**: Azure OpenAI GPT-5-Nano
- **Fallback**: Google Gemini 2.5 Flash (multiple keys)
- **Interactive**: Groq-powered LangGraph agent

### Caching Strategy
- **Memory Cache**: In-process document storage
- **Disk Cache**: Persistent embeddings and indices
- **Cache Keys**: MD5 hash of document URLs

## Performance Features

- **Batch Embeddings**: Configurable batch sizes for large documents
- **Parallel Processing**: Concurrent question handling
- **Smart Caching**: Avoid reprocessing identical documents
- **Streaming Downloads**: Memory-efficient file handling

## Monitoring & Logging

- **Request Logs**: JSON-formatted API request tracking
- **Debug Logs**: Detailed parser and processing logs
- **Real-time Dashboard**: WebSocket-powered monitoring
- **Performance Metrics**: Response times and token usage

## Error Handling

- **Graceful Degradation**: LLM fallback mechanisms
- **Format Validation**: Unsupported file type detection
- **Rate Limiting**: API key rotation for Gemini
- **Timeout Management**: Request timeout handling

## Development

### Running Tests
```bash
python -m pytest test/
```

### Code Structure
- **Modular Design**: Separate concerns for parsing, embeddings, retrieval
- **Async Support**: WebSocket and agent operations
- **Type Hints**: Full type annotation coverage
- **Error Logging**: Comprehensive error tracking

## License

See LICENSE file for details.