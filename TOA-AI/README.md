# TOA-AI: Technical Order Assistant AI

TOA-AI is a Retrieval-Augmented Generation (RAG) system designed to assist maintenance personnel in accessing and understanding information from Technical Orders (TOs). The system processes PDF documents, extracts structured content, and provides a powerful search and retrieval interface to quickly find relevant information.

## Features

- **PDF Processing Pipeline**: Extracts text, tables, images, and warnings from Technical Order PDFs
- **Hybrid Search**: Combines semantic search (FAISS) and lexical search (BM25) for optimal retrieval
- **Structured Data**: Maintains context with proper metadata for all extracted content
- **API Interface**: Provides a RESTful API for integration with other systems
- **LLM Integration**: Integrates with OpenAI and Anthropic APIs for natural language responses

## System Architecture

The TOA-AI system consists of the following components:

1. **Document Processing**: Extracts and structures content from PDF documents
   - Text extraction with OCR capabilities
   - Table detection and extraction
   - Warning/caution/note identification
   - Metadata extraction (document ID, page numbers, etc.)

2. **Embedding Generation**: Creates vector embeddings for all document chunks
   - Uses Sentence Transformers for semantic embeddings
   - Tokenizes text for BM25 lexical search

3. **Vector Store**: Stores and indexes document chunks for efficient retrieval
   - FAISS for semantic search
   - BM25 for lexical search
   - Hybrid search combining both approaches

4. **Retrieval System**: Finds relevant document chunks based on user queries
   - Supports filtering by document ID and asset type
   - Ranks results by relevance
   - Formats context for LLM consumption

5. **LLM Integration**: Connects to language models for natural language responses
   - OpenAI integration (GPT-4 series models)
   - Anthropic integration (Claude series models)
   - Configurable through environment variables or command line

6. **API Layer**: Provides a RESTful interface to the system
   - Query endpoint for searching
   - Generate endpoint for LLM responses
   - Document and asset type listing
   - Formatted output for LLM integration

## Getting Started

### Prerequisites

- Python 3.8+
- Required packages (see `requirements.txt`)
- OpenAI API key and/or Anthropic API key

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy the example environment file and add your API keys:
   ```
   cp .env.example .env
   # Edit .env to add your API keys
   ```

### Processing Documents

To process Technical Order PDFs:

```
python TOA-AI/process_pdf.py --pdf_path DATA/your_document.pdf
```

### Building the Vector Store

After processing documents, build the vector store:

```
python TOA-AI/build_vector_store.py
```

### Running the RAG System with LLM

To run the RAG system with LLM integration:

```
python TOA-AI/run_rag_with_llm.py --query "Your query here" --provider openai
```

Options:
- `--top-k`: Number of results to return (default: 5)
- `--provider`: LLM provider (openai or anthropic)
- `--model`: Specific model to use
- `--temperature`: Temperature for generation (default: 0.2)
- `--document`: Filter by document ID
- `--type`: Filter by asset type (table, warning)

### Running the Query Engine

To query the system from the command line without LLM:

```
python TOA-AI/query_engine.py --query "Your query here"
```

Options:
- `--top-k`: Number of results to return (default: 3)
- `--document`: Filter by document ID
- `--type`: Filter by asset type (table, warning)
- `--format-output`: Format output for LLM

### Running the API Server

To start the API server:

```
python TOA-AI/api.py
```

The server will start on http://localhost:8000 by default.

### Testing the API

Use the test script to interact with the API:

```
python TOA-AI/test_api.py --query "Your query here"
```

For LLM responses:

```
python TOA-AI/test_api.py --query "Your query here" --generate --provider openai
```

Options:
- `--top-k`: Number of results to return (default: 3)
- `--document`: Filter by document ID
- `--type`: Filter by asset type (table, warning)
- `--list-documents`: List available documents
- `--list-asset-types`: List available asset types
- `--list-providers`: List available LLM providers
- `--generate`: Generate a response using an LLM
- `--provider`: LLM provider to use (openai or anthropic)
- `--model`: Specific model to use
- `--temperature`: Generation temperature (default: 0.2)

## Web Interface

TOA-AI includes a modern web interface for easier interaction with the system.

### Setting up the Web Interface

1. Make sure you have Flask and requests installed:
   ```
   pip install flask requests
   ```

2. Run the setup script to ensure all files are in place:
   ```
   python TOA-AI/setup_web_ui.py
   ```

3. Start the TOA-AI API and Web Interface with a single command:
   ```
   python TOA-AI/start_web_ui.py
   ```
   
   This will start both the API server on port 8000 and the web interface on port 5000.

4. Or, you can start them separately:
   ```
   # Start the API server
   python TOA-AI/api.py
   
   # In a separate terminal, start the web interface
   python TOA-AI/web_app.py
   ```

5. Navigate to http://localhost:5000 in your browser to access the web interface.

### Web Interface Features

- Modern, responsive design for desktop and mobile use
- Real-time chat interface with the TOA-AI system
- Select between OpenAI and Anthropic providers
- Filter queries by document ID and asset type
- View properly formatted responses with markdown support
- See source citations with relevance scores
- Error handling and connection monitoring

### Web Interface Structure

```
TOA-AI/web/
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── main.js
│   └── img/
└── templates/
    └── index.html
```

## API Endpoints

- `GET /`: Health check
- `GET /documents`: List available documents
- `GET /asset_types`: List available asset types
- `GET /llm_providers`: List available LLM providers
- `POST /query`: Search for information
- `POST /generate`: Generate a response using LLM

Example query request:
```json
{
  "query": "What are the safety precautions for hot refueling operations?",
  "top_k": 3,
  "document_id": "TO 00-25-172CL-3",
  "asset_type": "table",
  "format_for_llm": true
}
```

Example generation request:
```json
{
  "query": "What are the safety precautions for hot refueling operations?",
  "top_k": 3,
  "document_id": "TO 00-25-172CL-3",
  "asset_type": "table",
  "provider": "openai",
  "model": "gpt-4o",
  "temperature": 0.2
}
```

## LLM Integration

The system supports both OpenAI and Anthropic APIs for generating responses, with the following considerations:

### OpenAI Integration
- Default model: `gpt-4o`
- Environment variable: `OPENAI_API_KEY`
- Model environment variable: `OPENAI_MODEL`

### Anthropic Integration
- Default model: `claude-3-opus-20240229`
- Environment variable: `ANTHROPIC_API_KEY`
- Model environment variable: `ANTHROPIC_MODEL`

You can set a default provider with the `LLM_PROVIDER` environment variable.

## Project Structure

```
TOA-AI/
├── src/                      # Source code
│   ├── processors/           # Document processing modules
│   ├── retrieval/            # Vector store and retrieval system
│   └── llm/                  # LLM integration
├── DATA/                     # Technical Order PDFs
├── processed/                # Processed document chunks
├── embeddings/               # Generated embeddings
├── vector_store/             # Vector store files
├── web/                      # Web interface files
│   ├── static/               # Static assets for web interface
│   │   ├── css/              # CSS stylesheets
│   │   ├── js/               # JavaScript files
│   │   └── img/              # Images
│   └── templates/            # HTML templates
├── api.py                    # API server
├── build_vector_store.py     # Vector store builder
├── create_embeddings.py      # Embedding generation script
├── process_pdf.py            # PDF processing script
├── query_engine.py           # Command-line query interface
├── rag_demo.py               # RAG demonstration script
├── run_rag_with_llm.py       # RAG with LLM integration
├── setup_web_ui.py           # Web interface setup script
├── start_web_ui.py           # Combined starter for API and web interface
├── test_api.py               # API test script
├── web_app.py                # Web interface Flask application
├── .env.example              # Example environment variables
└── requirements.txt          # Dependencies
```

## Security and Compliance

- All processed TO data is stored securely
- No Personally Identifiable Information (PII) is stored or processed
- API keys should be kept secure and not committed to version control
- The system follows DoD AI guidelines and cybersecurity best practices

## Continuous Improvement

The TOA-AI system includes mechanisms for continuous improvement:

- Feedback loop for maintainers to validate responses
- Regular retraining of embedding models
- Monitoring of usage patterns and failure cases
- Support for multiple LLM providers for flexibility and comparison

## License

[Specify license information] 