# Troubleshooting

## Common Issues

### LM Studio Not Connected

**Error:**
```
Error: Could not connect to LM Studio...
```

**Solution:**
1. Start LM Studio application
2. Load a model (4B recommended, e.g., Qwen3-VL-4B)
3. Ensure model is running on `http://localhost:1234`
4. Verify connection: `curl http://localhost:1234/v1/models`

### Research Workflow Not Triggered

**Symptom:**
```
[Routes to simple Q&A instead of research...]
```

**Solution:**
Include research keywords in your query:
- "Based on newsroom and web search..."
- "What are..."
- "Tell me about..."
- "Why..."
- "How..."

Or use `/search` command to force research workflow:
```
/search latest developments in renewable energy
```

Check routing patterns with `/config` command.

### Newsroom Not Available

**Symptom:**
```
Step 1/3: Fetching newsroom articles...
  ⚠ Newsroom unavailable, skipping
```

**Solution:**
This is normal - workflow continues with web search only. Newsroom is optional and only used if configured.

### Can't Save Research

**Error:**
```
Error: Could not save research...
```

**Solution:**
1. Check `~/.zorora/research/` directory exists:
   ```bash
   mkdir -p ~/.zorora/research
   ```
2. Verify directory is writable:
   ```bash
   chmod 755 ~/.zorora/research
   ```
3. Check disk space: `df -h ~`

### HuggingFace Endpoint Errors

**Error:**
```
Error: LLM API client error (HTTP 400)
```

**Solution:**
1. Check HF endpoint URL in `/models` or `config.py`
2. Verify HF token is valid:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api-inference.huggingface.co/models/Qwen/Qwen2.5-Coder-32B-Instruct
   ```
3. Check endpoint is running (not paused)
4. Verify endpoint URL format: `https://your-endpoint.hf.space/v1/chat/completions`

### Web Search Rate Limiting

**Error:**
```
Error: Web search failed - rate limited
```

**Solution:**
- **Brave API:** Check your API key and quota (2000/month free tier)
  - Verify key at: https://brave.com/search/api/
  - Check usage in Brave dashboard
- **DuckDuckGo:** Automatic retry with exponential backoff
  - Wait a few minutes and try again
  - DuckDuckGo has rate limits but they're not documented

### Model Not Found

**Error:**
```
Error: Model not found in LM Studio
```

**Solution:**
1. Check model name in `config.py` matches LM Studio model name exactly
2. Use `/models` command to see available models
3. Load model in LM Studio before running Zorora

### Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'zorora'
```

**Solution:**
1. Install Zorora:
   ```bash
   pip install git+https://github.com/AsobaCloud/zorora.git
   ```
2. Verify installation:
   ```bash
   pip show zorora
   ```
3. Check Python path:
   ```bash
   which python
   python --version
   ```

### Configuration File Not Found

**Error:**
```
FileNotFoundError: config.py
```

**Solution:**
1. Copy example config:
   ```bash
   cp config.example.py config.py
   ```
2. Edit `config.py` with your settings
3. Ensure `config.py` is in the same directory as `main.py`

### Research Files Not Loading

**Error:**
```
Error: Could not load research...
```

**Solution:**
1. Check file exists:
   ```bash
   ls -la ~/.zorora/research/
   ```
2. Verify file format (should be markdown with JSON frontmatter)
3. Check file permissions: `chmod 644 ~/.zorora/research/*.md`

### Development Workflow Fails

**Error:**
```
Error: Not a git repository
```

**Solution:**
1. Initialize git repository:
   ```bash
   git init
   ```
2. Ensure you're in a project directory
3. `/develop` workflow requires git for rollback capability

### Slow Performance

**Symptom:**
- Research workflow takes > 2 minutes
- Code generation takes > 2 minutes

**Solution:**
1. Check LM Studio model size (4B recommended for orchestrator)
2. Verify local model is loaded (not downloading)
3. Check network connection for HuggingFace endpoints
4. Monitor RAM usage: `htop` or Activity Monitor
5. Close other applications to free RAM

### Context Overflow

**Error:**
```
Error: Context too long
```

**Solution:**
1. Clear conversation context: `/clear`
2. Start new session
3. Reduce `MAX_CONTEXT_MESSAGES` in `config.py` (default: 50)

## Getting Help

1. Check logs: `repl.log` in project directory
2. Run with verbose logging:
   ```python
   # In config.py
   LOGGING_LEVEL = logging.DEBUG
   ```
3. Check LM Studio logs
4. Verify all dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

## Debug Mode

Enable debug logging in `config.py`:

```python
import logging
LOGGING_LEVEL = logging.DEBUG
```

This will show:
- All routing decisions
- Tool calls and responses
- Model API calls
- Error stack traces

## Performance Tuning

### Reduce RAM Usage
- Use 4B orchestrator model (not 8B+)
- Disable unused specialist models
- Reduce `MAX_CONTEXT_MESSAGES` in config

### Speed Up Responses
- Use local models instead of HuggingFace endpoints
- Enable web search caching (default: enabled)
- Use `/ask` for simple questions (no web search)

### Improve Reliability
- Use deterministic slash commands (`/search`, `/code`) instead of natural language
- Configure Brave Search API for reliable web search
- Use local models for critical workflows
