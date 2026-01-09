# Bank RAG - Multiagentic Pipeline for Financial Document Parsing

A sophisticated multiagentic pipeline designed for automated financial research and company metric extraction. The system employs specialized AI agents orchestrated through LangGraph workflows to extract structured information from web sources while ensuring source credibility and answer completeness.

## 🎯 Features

- **Multi-Agent Architecture**: 9 specialized agents working together to handle different aspects of information extraction
- **Hybrid Retrieval**: Combines semantic similarity and credibility scoring for optimal document ranking
- **Iterative Refinement**: Automatic quality control loops that improve answer completeness
- **Credibility Scoring**: Systematic evaluation of source trustworthiness (0.0-1.0 scale)
- **Dual Interaction Modes**:
  - **Full Search**: Comprehensive question-answering for detailed research
  - **Table Filling**: Batch processing with asynchronous cell-level extraction
- **Structured Outputs**: Extracts company metrics (revenue, market cap, employees, CEO) with explicit source citations
- **Web Interface**: Streamlit-based UI for easy interaction

## 🏗️ Architecture

The system consists of three main layers:

1. **Graph Layer**: Three LangGraph workflows (metrics graph, table graph, websearch tool graph)
2. **Agent Layer**: 9 specialized agents using OpenAI models (GPT-4o-mini, GPT-4o, GPT-5)
3. **Utility Layer**: Document parsing, retrieval, and credibility scoring functions

### Graph Workflows

- **Metrics Graph**: General question-answering with iterative refinement
- **Table Graph**: Structured metric extraction optimized for batch processing
- **Websearch Tool Graph**: Simplified workflow for speed-critical applications

## 📋 Prerequisites

- Python >= 3.13
- OpenAI API key
- Exa Search API key
- ScrapingAnt API key (optional, for web scraping fallback)

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Bank_RAG
   ```

2. **Install dependencies**:
   
   Using `uv` (recommended):
   ```bash
   uv sync
   ```
   
   Or using `pip`:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   
   Copy the example environment file:
   ```bash
   cp .env_example .env
   ```
   
   Edit `.env` and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   EXA_API_KEY=your_exa_api_key_here
   SCRAPER_ANT_API_KEY=your_scrapingant_api_key_here  # Optional
   ```

## 🔑 API Keys

### Required

- **OPENAI_API_KEY**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
  - Used for all AI agents (GPT-4o-mini, GPT-4o, GPT-5)
  - Required for answer generation, credibility scoring, and question rewriting

- **EXA_API_KEY**: Get your API key from [Exa AI](https://exa.ai/)
  - Used for semantic web search and document retrieval
  - Required for finding relevant financial documents

### Optional

- **SCRAPER_ANT_API_KEY**: Get your API key from [ScrapingAnt](https://www.scrapingant.com/)
  - Used as fallback for web scraping when direct URL access fails
  - System will work without this, but may have reduced reliability for some web sources

## 💻 Usage

### Running the Streamlit Application

Navigate to the `app` directory and run:

```bash
cd app
streamlit run streamlit_app.py
```

The application will open in your default web browser at `http://localhost:8501`

### Using Full Search Mode

1. Select "Full search" from the sidebar
2. Enter your query in natural language (e.g., "What is the revenue of Volkswagen Group?")
3. Click "Search"
4. The system will:
   - Search the web for relevant documents
   - Score documents for credibility
   - Generate a comprehensive answer with source citations
   - Automatically refine the answer if incomplete

### Using Table Filling Mode

1. Select "Table format" from the sidebar
2. Either:
   - Upload an Excel file with company names in the first column and metrics as headers
   - Or manually enter companies and metrics separated by `++`
3. Select which graph to use (Table Graph or Websearch Tool Graph)
4. Enter a project name
5. Click "Fill table"
6. The system will process all company-metric combinations asynchronously
7. Download the completed table as an Excel file

**Example Input**:
- Companies: `Volkswagen Group++BMW Group++Siemens`
- Metrics: `revenue++market_cap++employees++CEO`

### Programmatic Usage

#### Using Metrics Graph

```python
from graphs.metrics_graph import websearch_graph

config = {"configurable": {"thread_id": "unique_thread_id"}}
result = await websearch_graph.ainvoke(
    input={"question": "What is the revenue of Volkswagen Group?"},
    config=config
)

print(result["generation"])  # Generated answer
print(result["documents"])   # Retrieved documents
```

#### Using Table Graph

```python
from graphs.table_graph import one_metrics_graph

config = {"configurable": {"thread_id": "unique_thread_id"}}
result = await one_metrics_graph.ainvoke(
    input={
        "company_name": "Volkswagen Group",
        "metrics": "revenue"
    },
    config=config
)

print(result["generation"]["value"])    # Extracted value
print(result["generation"]["comment"])  # Source citations
```

#### Batch Processing

```python
from src.utils import process_lists
from graphs.table_graph import one_metrics_graph

companies = ["Volkswagen Group", "BMW Group", "Siemens"]
metrics = ["revenue", "market_cap", "employees"]

results = await process_lists(companies, metrics, one_metrics_graph)
# Results contain all company-metric combinations
```

## 📊 System Parameters

Default system parameters:

- **Exa Search**: 15 results per query
- **Hybrid Retrieval**: 
  - Initial retrieval: 30 documents (k_init)
  - Final selection: 15 documents (k_final)
  - Minimum credibility: 0.5
  - Credibility weight (α): 0.5
- **Max Retries**: 1 (for iterative refinement)
- **Embedding Model**: text-embedding-3-small
- **Temperature**: 0.0 (for all models, ensuring deterministic outputs)

## 🧪 Testing

The system includes testing notebooks in `app/testing_notebooks/`:

- `gpt_websearch.ipynb`: Testing GPT WebSearch Tool approach
- `table_filling_experiment.ipynb`: Testing table filling functionality
- `websearch_agent.ipynb`: Testing web search agents
- `search_results_receiving.ipynb`: Testing search result processing

## 📁 Project Structure

```
Bank_RAG/
├── app/
│   ├── graphs/              # LangGraph workflow definitions
│   │   ├── metrics_graph.py
│   │   ├── table_graph.py
│   │   └── websearch_tool_graph.py
│   ├── src/                 # Core functionality
│   │   ├── agents.py        # AI agent definitions
│   │   ├── parsing_utils.py # Document parsing and retrieval
│   │   ├── utils.py         # Utility functions
│   │   └── logger_initialization.py
│   ├── data/                # Dataset files
│   │   └── european_company_metrics_2025.csv
│   ├── testing_notebooks/   # Jupyter notebooks for testing
│   └── streamlit_app.py     # Streamlit web interface
├── figures/                 # Documentation figures
│   └── websearch_graph.png
├── report.tex              # LaTeX report
├── requirements.txt        # Python dependencies
├── pyproject.toml         # Project configuration
└── README.md              # This file
```

## 🔧 Configuration

### Model Selection

The system uses different OpenAI models based on task complexity:

- **GPT-4o-mini**: Lightweight tasks (retrieval grading, hallucination detection)
- **GPT-4o**: Moderate complexity (credibility assessment)
- **GPT-5**: High complexity (answer generation, question rewriting, full information grading)
- **GPT-5 Responses**: Tool-enabled agents (web search capabilities)

### Credibility Scoring

Documents are scored on a 0.0-1.0 scale based on:

- **Domain Reliability**: Official sources, trusted news, peer-reviewed content
- **Author Expertise**: Known experts vs. anonymous authors
- **Content Recency**: Fresh content preferred (unless older is more authoritative)

### Hybrid Retrieval

The hybrid score combines semantic similarity and credibility:

```
Hybrid Score = (1 - α) × Credibility + α × (1 - Similarity Distance)
```

Where α = 0.5 (equal weighting)

## 📝 Logging

Logs are stored in `app/logs/` with daily rotation. Each component has its own log file:

- `main_graph_*.log`: Main graph execution logs
- `parsing_utils_*.log`: Document parsing logs
- `streamlit_app_*.log`: Web interface logs
- `table_graph_*.log`: Table graph execution logs

## 🐛 Troubleshooting

### Common Issues

1. **API Key Errors**:
   - Ensure all required API keys are set in `.env`
   - Check that keys are valid and have sufficient credits

2. **Import Errors**:
   - Make sure you're running from the `app` directory or have the project root in your Python path
   - Verify all dependencies are installed: `pip install -r requirements.txt`

3. **Streamlit Issues**:
   - Clear Streamlit cache: `streamlit cache clear`
   - Check that port 8501 is not in use

4. **Async Errors**:
   - Ensure you're using Python 3.13 or higher
   - Check that event loops are properly managed in async contexts

### Getting Help

- Check the logs in `app/logs/` for detailed error messages
- Review the testing notebooks for usage examples
- Consult the LaTeX report (`report.tex`) for detailed system documentation

## 🚧 Limitations

- Average latency may be prohibitive for real-time applications
- Maximum 1 retry per query (configurable via MAX_RETRIES)
- In-memory vector stores are recreated per query (no persistence)
- Focuses primarily on web sources (proprietary databases not integrated)

## 🔮 Future Enhancements

- Persistent vector stores with caching
- Integration with proprietary financial databases
- Adaptive retry limits based on query complexity
- Streaming responses for long-form answers
- Custom embeddings fine-tuned for financial domain

