# StocksFlags
StocksFlags is a multi-agent AI equity analysis tool designed to provide comprehensive insights into the stock market. It leverages Large Language Models (LLMs) and agentic workflows to automate data gathering, processing, and analysis, ultimately generating investment signals and supporting user queries through a chatbot interface.

## Key Technologies

*   **Programming Language:** Python
*   **AI/LLM Frameworks:** LangChain, LangGraph
*   **Data Sources:** Multiple APIs (e.g., Polygon, Yahoo Finance), Custom MCP Integration, WRDS (Wharton Research Data Services)
*   **Database:** MySQL

## Core Functionality

The project aims to deliver functionality across three core components:

1.  **LLM Agent-Driven Analysis Tool:**
    *   Acts as the primary user interface for research and analysis.
    *   Accepts user queries in natural language.
    *   Utilizes LLM agents to autonomously:
        *   Determine the required information.
        *   Select and execute appropriate data retrieval tools (fetching market data, news, fundamentals from APIs like Polygon, Yahoo Finance, WRDS, and the internal database).
        *   Process the retrieved information using defined analysis tools (e.g., summarization, sentiment analysis, event extraction).
        *   Synthesize findings to answer the user's query.
    *   Integrates with the other components (Trading Signals and Valuation Model) as callable tools within its workflow.

2.  **LLM Agent-Driven Trading Signal Generation:**
    *   Employs specialized LLM agents (`src/agent`) to generate investment/trading signals.
    *   Agents analyze data based on various strategies:
        *   Simulating renowned investor approaches.
        *   Fundamental analysis.
        *   Macroeconomic assessment.
        *   Technical analysis.
        *   News sentiment interpretation.
    *   Can be executed directly or invoked as a tool by the main Analysis Tool.

3.  **Damodaran Valuation Model:**
    *   Implements valuation methodologies inspired by Professor Aswath Damodaran.
    *   Provides a user interface (details TBD) for manual input and valuation generation.
    *   Offers a callable tool interface, allowing the LLM Agent-Driven Analysis Tool to programmatically generate valuations as part of its research process.

## Repository Structure
```
StocksFlags/
├── data                                    # Data directory
├── models                                  # Valuation Model directory
├── notebooks/                              # Jupyter notebooks for demonstration
|    ├── checkpoint/
|    |    └── milestone_3.ipynb             # Checkpoint for milestone 3
|    ├── demo/                              # Notebook for demo and testing
|    ├── scrapers/                          # Scrapers (unfinished)
|    └── db_management.ipynb                # Database management tool                 
├── src/                                    # Source code
|    ├── data_tool/
|    |    ├── data_providers/
|    |    |    ├── connect_wrds.py          # code to connect wrds
|    |    |    ├── financial_datasets.py    # code to retrieve data from financial datasets
|    |    |    ├── polygon.py               # code to retrieve data from polygon
|    |    |    └── yahoo_finance.py         # code to retrieve data from yahoo finance
|    |    ├── data_models.py                # pydantic models
|    |    └── get_data.py                   # get data
|    ├── database_tool/                     
|    |    ├── connect_db.py                 # connect to database
|    |    ├── create_table.py               # create tables
|    |    └── db_operation.py               # complax data retrieval from database
|    └── llm/
|         ├── llm_models.py                 # LLM models
|         └── api_call.py                   # Make api call to LLM
|  
└── ...
```

## Getting Started

### 1. Clone the Repository
```bash
# Clone the repository to your local machine
git clone https://github.com/Chen-zexi/StocksFlags.git

# Navigate to the project directory
cd StocksFlags
```

### 2. Environment Setup
```bash
# Create environment from the environment.yml file
conda env create -f environment.yml

# Activate the environment
conda activate stocksflags
```

### 3. Set up API Keys
Set up API keys
Paste the API Keys into .env.example
Remove the .example extension

## Common Git Commands

### Basic Git Workflow
```bash
# Check status of your working directory
git status

# Add files to staging area
git add filename.py            # Add specific file
git add .                      # Add all modified files

# Commit changes with a message
git commit -m "Your descriptive commit message here"

# Push commits to remote repository
git push origin master           # Push to main branch
git push origin your-branch    # Push to a specific branch

# Pull latest changes from remote repository
git pull origin master           # Pull from main branch

# Create and switch to a new branch
git checkout -b new-branch-name

# Switch between branches
git checkout branch-name
```

### Other Useful Git Commands
```bash
# View commit history
git log

# Discard changes in working directory
git checkout -- filename.py

# Fetch updates from remote without merging
git fetch

# Merge a branch into your current branch
git merge branch-name

# View differences between working directory and last commit
git diff
```

## Team Members: 
- Alan zc2610@nyu.edu
- Jackson jc13246@nyu.edu
- Tyler tan4742@nyu.edu
- April asl8466@nyu.edu
- Vinci cc9100@nyu.edu