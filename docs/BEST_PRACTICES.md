# Best Practices

## Query Formulation

### Use Research Keywords

Start queries with research keywords to trigger research workflow:
- "What", "Why", "How", "Tell me"
- "Based on newsroom and web search..."
- Ask questions rather than give commands

**Good:**
```
> What are the major AI trends in 2025?
> Based on the newsroom as well as web search, what's happening with battery storage?
```

**Less reliable:**
```
> AI trends 2025
> Battery storage info
```

### Use Slash Commands for Explicit Control

When you need a specific workflow, use slash commands:
- `/search` - Force research workflow
- `/code` - Force code generation
- `/ask` - Force conversational mode
- `/develop` - Force development workflow

**Example:**
```
/search latest developments in solar energy
```

### Be Specific

More specific queries yield better results:
- Include context and domain
- Specify what you need (code, research, explanation)
- Mention sources if needed

**Good:**
```
> Write a Python function to validate email addresses using regex
> Based on newsroom and web search, what are FERC Order 2222 requirements for battery storage?
```

**Less specific:**
```
> Email validation
> FERC 2222
```

## Research Management

### Save Important Findings

Always save important research:
- Say "yes" when prompted after synthesis
- Or use: "Save this as [topic_name]"
- Research files stored in `~/.zorora/research/`

**Example:**
```
[Research synthesis...]

Would you like to save this research? (yes/no)
> yes
Topic name: AI Trends 2025
```

### Use Descriptive Topic Names

Use clear, descriptive names when saving:
- Include year/date if relevant
- Use domain-specific terms
- Keep names concise but informative

**Good:**
```
> Save this as "california_battery_storage_2025"
> Save this as "ferc_order_2222_requirements"
```

**Less descriptive:**
```
> Save this as "research"
> Save this as "stuff"
```

### Review Saved Research Regularly

Periodically review and organize saved research:
```bash
# List all research
> List all my saved research

# Load specific research
> Load my research on AI trends

# Delete outdated research
> Delete my research on old_topic
```

### Organize by Topic

Group related research by topic:
- Use consistent naming conventions
- Include dates in filenames
- Keep related research together

## Code Generation

### Provide Context

Include relevant context for code generation:
- Specify language and framework
- Mention existing code patterns
- Include requirements and constraints

**Good:**
```
> Write a Python function that parses energy consumption CSV files and calculates monthly totals using pandas
```

**Less context:**
```
> Parse CSV
```

### Use /develop for Complex Changes

For multi-file changes or refactoring, use `/develop`:
- Explores codebase automatically
- Creates detailed plan
- Gets approval before changes
- Validates with linting

**Example:**
```
/develop add REST API endpoint for user authentication
```

### Review Generated Code

Always review generated code:
- Check for errors
- Verify it matches requirements
- Test functionality
- Consider edge cases

## Configuration

### Configure Once, Use Forever

Set up configuration once:
- Run `/models` to configure endpoints
- Use 4B local model for orchestrator (RAM efficiency)
- Use 32B HF endpoint for Codestral (code quality)
- Save configuration in `config.py`

### Use Appropriate Models

Match models to tasks:
- **Orchestrator:** 4B model (RAM efficient, fast routing)
- **Codestral:** 32B model (code quality, can be remote)
- **Reasoning:** 4B-8B model (synthesis, can be local)

### Configure Web Search

Set up Brave Search API for reliable web search:
- Get free API key: https://brave.com/search/api/
- Free tier: 2000 queries/month (~66/day)
- DuckDuckGo fallback automatically used if unavailable

## Performance Optimization

### Use Local Models When Possible

Local models are faster and more reliable:
- 4B orchestrator: 10-30s responses
- Remote 32B Codestral: 60-90s responses
- Balance quality vs speed based on needs

### Enable Caching

Web search caching is enabled by default:
- Reduces API calls for repeated queries
- 1 hour cache for general queries
- 24 hour cache for stable queries (documentation)

### Monitor RAM Usage

Keep RAM usage in check:
- Use 4B orchestrator model (4-6 GB)
- Close other applications
- Monitor with `htop` or Activity Monitor

## Workflow Selection

### Use Deterministic Commands

Prefer slash commands for reliability:
- `/search` - Always triggers research
- `/code` - Always triggers code generation
- `/ask` - Always triggers conversational mode

### Understand Routing Patterns

Learn which patterns trigger which workflows:
- File operations: "save", "load", "list", "show"
- Code generation: "write", "create", "generate" + "code"
- Research: "what", "why", "how", "tell me"
- Check patterns with `/config` command

### Separate Code from Research

Use appropriate workflows:
- Code tasks → `/code` or natural language with "write/create/generate"
- Research tasks → `/search` or questions
- Simple Q&A → `/ask` or direct questions

## Error Handling

### Check Logs

When errors occur, check logs:
- `repl.log` in project directory
- LM Studio logs
- Enable debug logging in `config.py` if needed

### Verify Configuration

Ensure configuration is correct:
- Check `config.py` exists and is valid
- Verify model names match LM Studio
- Test API keys and endpoints

### Use Fallbacks

Zorora has built-in fallbacks:
- DuckDuckGo if Brave Search unavailable
- Local models if HF endpoints fail
- Simple Q&A if research workflow fails

## Research Quality

### Verify Sources

Check source citations:
- Research workflow includes [Newsroom] and [Web] tags
- Review source URLs when provided
- Cross-reference multiple sources

### Synthesize Multiple Queries

For complex topics, break into multiple queries:
- Research different aspects separately
- Save each as separate research file
- Combine insights manually if needed

### Use EnergyAnalyst for Policy Queries

For energy policy questions, use `/analyst`:
- Accesses 485+ policy documents
- More accurate than web search
- Requires EnergyAnalyst API server

## Development Workflow

### Use Git

Always use `/develop` in a git repository:
- Enables rollback if needed
- Tracks changes
- Provides safety net

### Review Plans Carefully

Before approving `/develop` plans:
- Review files to be created/modified
- Check dependencies
- Verify execution order
- Consider edge cases

### Test After Changes

After `/develop` execution:
- Review generated code
- Run tests if available
- Check linting results
- Verify functionality

## Storage Management

### Monitor Research Storage

Check `~/.zorora/research/` periodically:
- Review saved research
- Delete outdated files
- Organize by topic
- Keep storage manageable

### Backup Important Research

Backup critical research:
- Copy `~/.zorora/research/` to backup location
- Use version control for important research
- Export to other formats if needed

## Advanced Usage

### Combine Workflows

Chain workflows for complex tasks:
1. Research topic: `/search AI trends 2025`
2. Save research: `Save this as "ai_trends_2025"`
3. Generate code: `/code create a script to analyze AI trends`
4. Use research: Reference saved research in code generation

### Use Conversation History

Leverage conversation context:
- Previous queries inform current responses
- Use `/history` to review past sessions
- Resume conversations with `/resume`

### Customize Configuration

Adjust configuration for your needs:
- Modify routing patterns in `simplified_router.py`
- Add custom tools in `tool_registry.py`
- Configure specialist models in `config.py`
