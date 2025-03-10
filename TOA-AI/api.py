#!/usr/bin/env python3
import os
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from src.retrieval import Retriever
from src.llm import RAGPromptTemplate, LLMConnector, LLMProvider
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TOA-AI API",
    description="API for Technical Order Assistant AI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize retriever
vector_store_path = os.environ.get("VECTOR_STORE_PATH", "TOA-AI/vector_store")
model_name = os.environ.get("MODEL_NAME", "all-MiniLM-L6-v2")
retriever = Retriever(vector_store_path, model_name=model_name)

# Check if retriever loaded successfully
if not retriever.vector_store:
    logger.error(f"Failed to load vector store from {vector_store_path}")
    raise RuntimeError(f"Failed to load vector store from {vector_store_path}")
else:
    logger.info(f"Loaded vector store with {len(retriever.vector_store.chunks)} chunks")

# Define request and response models
class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    alpha: float = 0.5
    document_id: Optional[str] = None
    asset_type: Optional[str] = None
    format_for_llm: bool = True

class ChunkMetadata(BaseModel):
    document_id: str
    page_num: int
    asset_type: str
    section: Optional[str] = None
    warning_type: Optional[str] = None

class ChunkResponse(BaseModel):
    id: str
    content: str
    metadata: ChunkMetadata
    score: float

class QueryResponse(BaseModel):
    query: str
    results: List[ChunkResponse]
    context: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None

class LLMRequest(BaseModel):
    query: str
    top_k: int = 5
    alpha: float = 0.5
    document_id: Optional[str] = None
    asset_type: Optional[str] = None
    temperature: float = 0.2
    provider: str = "openai"
    model: Optional[str] = None

class LLMResponse(BaseModel):
    query: str
    response: str
    results: List[ChunkResponse]
    context: str

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "TOA-AI API is running"}

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Query the TOA-AI system
    
    This endpoint accepts a query and returns relevant chunks from the Technical Orders.
    """
    try:
        # Prepare filter if any
        filter_by = {}
        if request.document_id:
            filter_by["document_id"] = request.document_id
        if request.asset_type:
            filter_by["asset_type"] = request.asset_type
        
        # Retrieve relevant chunks
        results = retriever.retrieve(
            request.query, 
            k=request.top_k, 
            alpha=request.alpha, 
            filter_by=filter_by
        )
        
        if not results:
            return QueryResponse(
                query=request.query,
                results=[],
                context=None,
                messages=None
            )
        
        # Format context for LLM if requested
        context = None
        messages = None
        if request.format_for_llm:
            context = retriever.format_retrieved_context(results)
            messages = RAGPromptTemplate.format_messages(request.query, context)
        
        # Format response
        formatted_results = []
        for result in results:
            metadata = result.get('metadata', {})
            formatted_results.append(
                ChunkResponse(
                    id=result.get('id', ''),
                    content=result.get('content', ''),
                    metadata=ChunkMetadata(
                        document_id=metadata.get('document_id', 'Unknown'),
                        page_num=metadata.get('page_num', 0),
                        asset_type=metadata.get('asset_type', 'content'),
                        section=metadata.get('section', None),
                        warning_type=metadata.get('warning_type', None)
                    ),
                    score=result.get('score', 0.0)
                )
            )
        
        return QueryResponse(
            query=request.query,
            results=formatted_results,
            context=context,
            messages=messages
        )
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate", response_model=LLMResponse)
async def generate(request: LLMRequest):
    """
    Generate a response from the LLM based on the query and retrieved context
    
    This endpoint accepts a query, retrieves relevant chunks, and generates a response using the specified LLM.
    """
    try:
        # Prepare filter if any
        filter_by = {}
        if request.document_id:
            filter_by["document_id"] = request.document_id
        if request.asset_type:
            filter_by["asset_type"] = request.asset_type
        
        # Retrieve relevant chunks
        results = retriever.retrieve(
            request.query, 
            k=request.top_k, 
            alpha=request.alpha, 
            filter_by=filter_by
        )
        
        if not results:
            raise HTTPException(status_code=404, detail="No relevant information found for this query")
        
        # Format context for LLM
        context = retriever.format_retrieved_context(results)
        
        # Initialize LLM connector
        llm = LLMConnector(provider=request.provider, model=request.model)
        
        # Generate response
        response = llm.rag_query(request.query, context, temperature=request.temperature)
        
        # Format results for response
        formatted_results = []
        for result in results:
            metadata = result.get('metadata', {})
            formatted_results.append(
                ChunkResponse(
                    id=result.get('id', ''),
                    content=result.get('content', ''),
                    metadata=ChunkMetadata(
                        document_id=metadata.get('document_id', 'Unknown'),
                        page_num=metadata.get('page_num', 0),
                        asset_type=metadata.get('asset_type', 'content'),
                        section=metadata.get('section', None),
                        warning_type=metadata.get('warning_type', None)
                    ),
                    score=result.get('score', 0.0)
                )
            )
        
        return LLMResponse(
            query=request.query,
            response=response,
            results=formatted_results,
            context=context
        )
    
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def get_documents():
    """
    Get a list of all available documents
    """
    try:
        # Extract unique document IDs from chunks
        document_ids = set()
        for chunk in retriever.vector_store.chunks:
            metadata = chunk.get('metadata', {})
            doc_id = metadata.get('document_id')
            if doc_id:
                document_ids.add(doc_id)
        
        return {"documents": sorted(list(document_ids))}
    
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/asset_types")
async def get_asset_types():
    """
    Get a list of all available asset types
    """
    try:
        # Extract unique asset types from chunks
        asset_types = set()
        for chunk in retriever.vector_store.chunks:
            metadata = chunk.get('metadata', {})
            asset_type = metadata.get('asset_type')
            if asset_type:
                asset_types.add(asset_type)
        
        return {"asset_types": sorted(list(asset_types))}
    
    except Exception as e:
        logger.error(f"Error getting asset types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/llm_providers")
async def get_llm_providers():
    """
    Get a list of available LLM providers
    """
    return {"providers": [provider.value for provider in LLMProvider]}

if __name__ == "__main__":
    # Run the API server
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("api:app", host=host, port=port, reload=True) 