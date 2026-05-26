# REPL Data Analysis Capabilities

## Overview

Zorora's REPL includes powerful data analysis capabilities that allow users to load, profile, and analyze datasets directly from the terminal interface. This functionality provides full-stack data analysis without leaving the REPL environment.

## Core Commands

### `/load <path>` - Load and Profile Dataset
Load a CSV dataset and automatically profile it for analysis.

**Usage:**
```
/load ./data/sales_data.csv
```

**Features:**
- Automatic file format detection (CSV)
- Comprehensive profiling including:
  - Row and column counts
  - Data type detection for each column
  - Null value analysis and percentages
  - Numeric column statistics (mean, median, std, min, max, quartiles)
  - Time series detection and resolution analysis
  - Categorical value frequency analysis
- Session storage for subsequent analysis
- Automatic timestamp parsing for datetime columns

### `/analyze <code>` - Run Sandboxed Analysis
Execute Python code on the loaded dataset in a secure sandbox environment.

**Usage:**
```
/analyze df.groupby('category')['sales'].sum().reset_index()
```

**Example Analyses:**
```
/analyze df.describe()                           # Summary statistics
/analyze df[df['sales'] > 1000]                  # Filtering
/analyze df['sales'].corr(df['marketing'])       # Correlation
/analyze df.groupby('region').size().reset_index(name='count')  # Grouping
/analyze df.plot(kind='scatter', x='ads', y='sales')  # Visualization
```

## Data Analysis Engine Components

### Data Profiler (`tools/data_analysis/profiler.py`)
Provides comprehensive dataset profiling:

**Capabilities:**
- **Basic Statistics**: Row/column counts, data types, missing values
- **Numeric Analysis**: Mean, median, mode, standard deviation, quartiles
- **Time Series Detection**: Identifies datetime columns, computes range, resolution, gap count
- **Format Detection**: Recognizes specialized formats (e.g., ODS-E for energy data)
- **Descriptive Statistics**: Full `df.describe()` equivalent output
- **Memory Usage**: Estimates memory footprint of the dataset

### Sandboxed Code Execution (`tools/data_analysis/execute.py`)
Secure environment for running analysis code:

**Security Features:**
- **Allowlisted Builtins Only**: `len`, `range`, `sum`, `min`, `max`, `round`, `sorted`, `enumerate`, `zip`, `map`, `filter`, `list`, `dict`, `set`, `tuple`, `str`, `int`, `float`, `bool`, `print`, `type`, `isinstance`, `abs`, `any`, `all`
- **Blocked Imports**: `os`, `sys`, `subprocess`, `shutil`, `importlib`, `pathlib`, `eval`, `exec`, `open`, `file` and other dangerous modules
- **Pre-injected Globals**: `df` (loaded DataFrame), `pd` (pandas), `np` (numpy), `plt` (matplotlib), `scipy.stats`
- **Smart Result Detection**: Returns typed JSON (`scalar`, `dataframe`, `series`, `list`, `dict`, `string`, `none`)
- **Plot Capture**: Automatically detects and saves `__zorora_plot__.png` with metadata
- **Configurable Timeout**: Default 30 seconds, adjustable via configuration

### Session Management (`tools/data_analysis/session.py`)
Persistent storage for analysis workflows:

**Features:**
- **Module-level Storage**: DataFrame and metadata persist between `/analyze` calls
- **Automatic Cleanup**: Old sessions cleared based on configuration
- **Multiple Dataset Support**: Can switch between different loaded datasets
- **Metadata Preservation**: Profiling results, load timestamp, source file info

### Nehanda Local Query (`tools/data_analysis/nehanda_local.py`)
Offline policy and document search capabilities:

**Features:**
- **FAISS-based Vector Search**: Fast similarity search over local document corpus
- **Sentence-Transformers Embeddings**: Uses `all-MiniLM-L6-v2` model with numpy fallback
- **Configurable Corpus**: Directory of `.txt` policy documents for search
- **Adjustable Parameters**: Chunk size, top-K results, similarity thresholds
- **Fallback Mechanism**: Numpy cosine similarity when FAISS unavailable

## Analysis Workflow

### Three-Stage Pipeline (`workflows/load_dataset.py`):
1. **Ingest/Detect**: Load file, detect format, basic validation
2. **Profile**: Comprehensive analysis using the profiler module
3. **Session Assembly**: Store DataFrame and metadata for analysis

### Key Features:
- **Automatic Timestamp Parsing**: Detects and parses `Timestamp`, `datetime`, `date`, `time` columns
- **File Replacement**: Loading a new file cleanly replaces the previous session
- **Timezone Handling**: Preserves timezone information when present
- **Format Validation**: Checks for common CSV issues (inconsistent columns, encoding problems)

## Tool Registry Integration

All data analysis functions are registered in the tool system:

**Registered Functions:**
- `profile_dataframe` → `tools.data_analysis.profiler.profile_dataframe`
- `execute_analysis` → `tools.data_analysis.executor.execute_analysis`
- `nehanda_query` → `tools.data_analysis.nehanda_local.nehanda_query`
- `load_dataset` → `workflows.load_dataset.LoadDatasetWorkflow.execute`

**Access Methods:**
- Direct tool use: `/use profile_dataframe --df "$(cat data.csv)"`
- Natural language: "profile this dataset" (after loading)
- Programmatic access via Python APIs

## Configuration

Settings in `config.py`:

```python
DATA_ANALYSIS = {
    "max_code_length": 10000,           # Maximum analysis code length
    "execution_timeout": 30,            # Seconds before timeout
    "plot_output_dir": "plots",         # Directory for saved plots
}

NEHANDA_LOCAL = {
    "corpus_dir": "",                   # Policy documents directory
    "index_cache_dir": "",              # FAISS index cache location
    "embedding_model": "all-MiniLM-L6-v2",  # Embedding model name
    "chunk_size": 512,                  # Text chunk size for processing
    "top_k_default": 5,                 # Default number of results to return
}
```

## Usage Examples

### Basic Workflow:
```
/load ./data/energy_production.csv
/analyze df.describe()
/analyze df[df['production'] > df['production'].quantile(0.9)]
/analyze df.groupby('fuel_type')['production'].mean().round(2)
```

### Time Series Analysis:
```
/load ./data/power_grid_hourly.csv
/analyze df.set_index('timestamp')['mw_load'].rolling(window=24).mean()
/analyze df['hour'] = df['timestamp'].dt.hour
/analyze df.groupby('hour')['mw_load'].mean().plot(kind='line')
```

### Correlation Analysis:
```
/load ./data/market_indicators.csv
/analyze df.corr()[['oil_price']].sort_values('oil_price', ascending=False)
/analyze df.plot.scatter(x='gas_price', y='electricity_price')
/analyze df['oil_price'].pct_change().rolling(7).mean().plot()
```

### Machine Learning Preparation:
```
/load ./data/ml_training_data.csv
/analyze df.isnull().sum()  # Check missing values
/analyze df = df.fillna(df.mean())  # Simple imputation
/analyze from sklearn.preprocessing import StandardScaler  # Not allowed in sandbox
# Instead: use built-in pandas operations
/analyze df_normalized = (df - df.mean()) / df.std()
```

## Plot Generation and Capture

Automatic plot detection enables visualization workflows:

### How It Works:
1. Analysis code creates a matplotlib plot
2. Plot is saved as `__zorora_plot__.png` in the configured output directory
3. System detects the file and returns `plot_generated: true` with file path
4. Plot can be displayed in compatible clients or retrieved later

### Example:
```
/analyze df.groupby('month')['sales'].sum().plot(kind='bar')
# Returns: {"plot_generated": true, "plot_path": "plots/__zorora_plot__.png", ...}
```

## Limitations and Considerations

### Security Boundaries:
- No filesystem access outside permitted operations
- No network calls from within sandbox
- No access to system modules or dangerous functions
- Resource limits prevent excessive memory or CPU usage

### Performance Notes:
- Large datasets (>100K rows) may experience slower profiling
- Complex visualizations with many data points may exceed timeout
- Memory usage scales with dataset size (monitor for very large files)
- First-time Nehanda corpus loading incurs embedding computation cost

### Data Type Handling:
- Mixed-type columns may be converted to strings for consistency
- Very large numbers may lose precision in JSON serialization
- Dates are serialized as ISO strings for consistency
- Binary data (images, etc.) should be handled through specialized tools

## Integration with Other Zorora Features

### Research Combination:
- Load external datasets to enrich research findings
- Use analysis results in follow-up chat contexts
- Combine data insights with newsroom and web research

### Workflow Chaining:
- `/load` → `/analyze` → `/deep` for research validation
- Research findings → `/load` for local data supplementation
- Analysis exports → `/code` for custom visualization scripts

### Export and Sharing:
- Analysis results can be saved via file operations
- Plots retrieved from output directory for reporting
- Session data persisted for collaborative workflows
- CSV export available through standard file operations