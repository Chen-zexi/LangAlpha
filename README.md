# StocksFlags
StocksFlags for PIP&DS
## Team Members: 
- Alan zc2610@nyu.edu
- Jackson jc13246@nyu.edu
- Tyler tan4742@nyu.edu
- April asl8466@nyu.edu
- Vinci cc9100@nyu.edu

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

