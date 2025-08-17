import requests
import logging
import os
from typing import List
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(override=True)

# Create logs directory
os.makedirs("logs", exist_ok=True)

# Configure logging for api_details.log
detail_logger = logging.getLogger("api_details")
if not detail_logger.handlers:
    detail_logger.setLevel(logging.INFO)
    detail_handler = logging.FileHandler("logs/api_details.log")
    detail_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    detail_logger.addHandler(detail_handler)
    detail_logger.propagate = False

llm = ChatOpenAI(api_key=os.getenv("GROQ_API_KEY"),
                 model_name="openai/gpt-oss-120b",
                 temperature=0,
                 max_completion_tokens=15000,
                 base_url="https://api.groq.com/openai/v1/",
                 streaming=True)
import numpy as np
from.embeddings import get_embeddings, build_faiss_index
from .document_parser import parse_pdf

# def retriever_tool(doc_url: str):
#     """Factory function that creates a retriever tool for a specific document"""
    
#     # Parse the document and build index
#     pages = parse_pdf(doc_url)
#     if not pages:
#         raise ValueError("Could not parse document")
    
#     chunk_embeddings = get_embeddings(tuple(pages))
#     if chunk_embeddings is None:
#         raise ValueError("Failed to generate embeddings")
    
#     index = build_faiss_index(chunk_embeddings)
    
#     @tool
#     def document_retriever(query: str) -> str:
#         """Search and retrieve relevant information from the loaded document"""
#         try:
#             q_embeddings = get_embeddings((query,))
#             if q_embeddings is None:
#                 return "Unable to process query"
            
#             q_embed = q_embeddings[0]
#             D, I = index.search(np.array([q_embed]), k=5)
#             relevant_chunks = [pages[i] for i in I[0]]
            
#             return "\n\n".join(relevant_chunks)
#         except Exception as e:
#             return f"Error retrieving information: {e}"
    
#     return document_retriever

@tool
def web_scraper_tool(url: str) -> str:
    """
    Fetches the complete text content from a given web URL or API endpoint.
    Use this tool to get data from external sources as instructed by the mission document.
    """
    print(f"\n--- TOOL: Web Scraper ---")
    print(f"Fetching content from: {url}")
    try:
        if url.lower().endswith('.pdf'):
            from .document_parser import parse_pdf
            pages = parse_pdf(url)
            return " ".join(pages) if pages else "No text content found in PDF."
        
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' in content_type:
            from .document_parser import parse_pdf
            pages = parse_pdf(url)
            return " ".join(pages) if pages else "No text content found in PDF."
        elif 'application/json' in content_type:
            json_data = response.json()
            
            # Log response
            detail_logger.info(f"{json_data}")
            
            return str(json_data)
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            
            # Log flight response text
            flight_response_text = text
            detail_logger.info(f"flight response: {flight_response_text}")
            
            return text if text else "Successfully fetched URL, but no text content was found."

    except Exception as e:
        return f"Error: Could not fetch the URL. {e}"

AGENT_SYSTEM_PROMPT = """You are a highly specialized reasoning agent. Your mission is to follow instructions from a given document to find a final answer.

*Your Workflow:*
1.  *Analyze the Mission:* Carefully read the 'INSTRUCTION DOCUMENT CONTENT' provided by the user. Understand the overall objective and all the required steps.
2.  *Execute Step-by-Step:* Follow the instructions precisely. For each step that requires fetching external data from a URL, you MUST use the ⁠ web_scraper_tool ⁠.
3.  *Reason and Combine:* Analyze the information you've gathered. Think about how it helps you complete the current step and move to the next one.
4.  *Conclude:* Once you have followed all steps and found the final piece of information required by the 'USER QUERY', state the answer clearly and concisely. Your final output should only be the answer itself.
5. The ans formate should be some thing like this(based on the question): "The flight number is: [flight number]"
*Critical Instructions:*
•⁠  ⁠Do not guess or hallucinate. Rely only on the information provided in the instructions and gathered from your tool.
•⁠  ⁠You have one tool: ⁠ web_scraper_tool ⁠. Use it to read the content of any URL.
•⁠  ⁠Announce when you are moving to a new step, e.g., "Now proceeding to Step 2."
"""


async def reasoning_agent(url: str, query: str) -> List[str]:
    
    tools = [web_scraper_tool]
    
    print(f"--- Pre-fetching instruction document from: {url} ---")
    # Ainvoke the async tool to pre-fetch the instructions without blocking.
    instruction_content = await web_scraper_tool.ainvoke({"url": url})
    
    if "Error:" in instruction_content or "failed" in instruction_content:
        error_message = f"Failed to load the initial instruction document. Aborting. Reason: {instruction_content}"
        print(error_message)
        return [error_message]

    print(f"--- Instructions Loaded Successfully ---")
    agent_executor = create_react_agent(llm, tools)

    print(f"{'='*20} Agent Initialized. Starting Task. {'='*20}\n")
    
    messages = [
        SystemMessage(content=AGENT_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""
                ### INSTRUCTION DOCUMENT CONTENT:
                ---
                {instruction_content}
                ---

                ### USER QUERY:
                {query}

                Please execute the mission based on the instructions above to answer the user's query.
                """
        )

    ]
    result = await agent_executor.ainvoke({"messages": messages})

    return result["messages"][-1].content
