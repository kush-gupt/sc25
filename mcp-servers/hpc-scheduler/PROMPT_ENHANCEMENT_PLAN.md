# Prompt Generation Enhancement Plan

## Executive Summary

Update the fips-agents-cli prompt generator to fully support FastMCP's prompt capabilities, including async prompts, Context access, multiple return types, and decorator arguments. Current implementation has significant gaps compared to FastMCP's documented features.

## Current State Analysis

### Critical Issues

1. **Return Type Mismatch**
   - CLI hardcodes: `return_type: "list[PromptMessage]"`
   - Template hardcodes: `-> str`
   - These contradict each other
   - FastMCP supports: `str`, `PromptMessage`, `list[PromptMessage | str]`, `Any`

2. **Missing Async Support**
   - CLI hardcodes: `"async": False`
   - No `--async/--sync` option
   - Template only generates `def`, not `async def`
   - FastMCP docs explicitly support both

3. **No Context Parameter Support**
   - Tools and resources have `--with-context`
   - Prompts don't, despite FastMCP docs showing it's common
   - Can't access `ctx.request_id`, notifications, etc.

4. **Limited Decorator Configuration**
   - Current: Bare `@mcp.prompt` only
   - Missing: `name`, `title`, `description`, `tags`, `enabled`, `meta`

### Inconsistencies with Other Components

**Tool/Resource Options:**
```bash
--async/--sync        ✓
--with-context        ✓
--description         ✓
--params              ✓
--return-type         ✓
--dry-run             ✓
```

**Current Prompt Options:**
```bash
--async/--sync        ✗
--with-context        ✗
--description         ✓
--params              ✓
--return-type         ✗
--with-schema         ✓ (prompt-specific)
--dry-run             ✓
```

---

## Proposed Changes

### Phase 1: CLI Command Updates

**File**: `src/fips_agents_cli/commands/generate.py`

#### 1.1 Add Missing Options

```python
@generate.command("prompt")
@click.argument("name")
@click.option(
    "--async/--sync",
    "is_async",
    default=False,
    help="Generate async or sync function (default: sync)"
)
@click.option(
    "--with-context",
    is_flag=True,
    help="Include FastMCP Context parameter"
)
@click.option(
    "--description", "-d",
    help="Prompt description"
)
@click.option(
    "--params",
    type=click.Path(exists=True),
    help="JSON file with parameter definitions"
)
@click.option(
    "--return-type",
    type=click.Choice(["str", "PromptMessage", "PromptResult", "list[PromptMessage]"]),
    default="str",
    help="Return type annotation (default: str)"
)
@click.option(
    "--with-schema",
    is_flag=True,
    help="Include JSON schema example in prompt body"
)
@click.option(
    "--prompt-name",
    help="Override decorator name (default: use function name)"
)
@click.option(
    "--title",
    help="Human-readable title for the prompt"
)
@click.option(
    "--tags",
    help="Comma-separated tags for categorization"
)
@click.option(
    "--disabled",
    is_flag=True,
    help="Generate prompt in disabled state"
)
@click.option(
    "--meta",
    help="JSON string of metadata (e.g., '{\"version\": \"1.0\"}')"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without creating files"
)
def prompt(
    name: str,
    is_async: bool,
    with_context: bool,
    description: str | None,
    params: str | None,
    return_type: str,
    with_schema: bool,
    prompt_name: str | None,
    title: str | None,
    tags: str | None,
    disabled: bool,
    meta: str | None,
    dry_run: bool,
):
    """
    Generate a new prompt component.

    NAME is the prompt name in snake_case (e.g., code_review, summarize_text)

    Examples:
        # Basic string prompt
        fips-agents generate prompt code_review --description "Review code for best practices"

        # Async prompt with Context
        fips-agents generate prompt fetch_data --async --with-context --return-type PromptMessage

        # Prompt with parameters and schema
        fips-agents generate prompt analyze_data --params params.json --with-schema

        # Advanced: custom name, tags, metadata
        fips-agents generate prompt generate_report \\
            --prompt-name "report_generator" \\
            --title "Report Generator" \\
            --tags "reporting,analysis" \\
            --meta '{"version": "2.0", "author": "data-team"}'
    """
    console.print("\n[bold cyan]Generating Prompt Component[/bold cyan]\n")

    # Parse tags
    tags_list = [t.strip() for t in tags.split(",")] if tags else None

    # Parse metadata
    meta_dict = None
    if meta:
        try:
            import json
            meta_dict = json.loads(meta)
        except json.JSONDecodeError as e:
            console.print(f"[red]✗[/red] Invalid JSON in --meta: {e}")
            sys.exit(1)

    template_vars = {
        "async": is_async,
        "with_context": with_context,
        "return_type": return_type,
        "with_schema": with_schema,
        "prompt_name": prompt_name,
        "title": title,
        "tags": tags_list,
        "enabled": not disabled,
        "meta": meta_dict,
    }

    generate_component_workflow("prompt", name, template_vars, params, dry_run, description)
```

#### 1.2 Return Type Validation

Add validation for return_type to ensure template compatibility:

```python
# In generate_component_workflow, after loading params
if component_type == "prompt":
    return_type = template_vars.get("return_type", "str")

    # Validate return type requires appropriate imports
    if return_type in ["PromptMessage", "PromptResult", "list[PromptMessage]"]:
        template_vars["needs_prompt_imports"] = True
```

---

### Phase 2: Template Updates

**File**: `.fips-agents-cli/generators/prompt/component.py.j2`

#### 2.1 Updated Imports

```jinja
"""{{ description }}"""

from pydantic import Field
{% if needs_prompt_imports -%}
from fastmcp import Context
from fastmcp.prompts.prompt import Message, PromptMessage, PromptResult, TextContent
{% endif -%}
{% if with_context and not needs_prompt_imports -%}
from fastmcp import Context
{% endif -%}
from core.app import mcp
```

#### 2.2 Updated Decorator

```jinja
@mcp.prompt{% if prompt_name or title or tags or not enabled or meta %}(
{%- if prompt_name %}
    name="{{ prompt_name }}",
{%- endif %}
{%- if title %}
    title="{{ title }}",
{%- endif %}
{%- if description %}
    description="{{ description }}",
{%- endif %}
{%- if tags %}
    tags={{ '{' }}{% for tag in tags %}"{{ tag }}"{% if not loop.last %}, {% endif %}{% endfor %}{{ '}' }},
{%- endif %}
{%- if not enabled %}
    enabled=False,
{%- endif %}
{%- if meta %}
    meta={{ meta }},
{%- endif %}
){% endif %}
```

#### 2.3 Function Signature

```jinja
{% if async %}async {% endif %}def {{ component_name }}(
{% for param in params %}    {{ param.name }}: {{ param.type_hint }} = Field(
{% if param.default is defined %}        default={{ param.default }},
{% endif %}        description="{{ param.description }}"
    ),
{% endfor %}{% if with_context %}    ctx: Context,
{% endif %}) -> {{ return_type }}:
```

#### 2.4 Function Body by Return Type

```jinja
    """{{ description }}

    Args:
{% if params|length > 0 %}{% for param in params %}        {{ param.name }}: {{ param.description }}
{% endfor %}{% endif %}{% if with_context %}        ctx: FastMCP Context object for accessing request metadata
{% endif %}
    Returns:
        {{ return_description|default('Formatted prompt for LLM interaction') }}
    """
{% if return_type == "str" %}
    return f"""{{ prompt_instruction|default('Analyze and process the following:') }}

{% for param in params %}{% if not param.get('optional', False) %}<{{ param.name }}>
{{ '{' }}{{ param.name }}{{ '}' }}
</{{ param.name }}>

{% endif %}{% endfor %}
{%- if with_schema %}
Return as JSON:
{{ '{' }}
  "result": "{{ result_field|default('Main result') }}",
  "details": "{{ details_field|default('Additional details') }}"
{{ '}' }}
{%- else %}
# TODO: Add specific prompt instructions
# Provide clear, structured guidance for the LLM
{%- endif %}"""

{% elif return_type == "PromptMessage" %}
    content = f"""{{ prompt_instruction|default('Analyze and process the following:') }}

{% for param in params %}{% if not param.get('optional', False) %}<{{ param.name }}>
{{ '{' }}{{ param.name }}{{ '}' }}
</{{ param.name }}>

{% endif %}{% endfor %}"""

    return PromptMessage(
        role="user",
        content=TextContent(type="text", text=content)
    )

{% elif return_type == "PromptResult" or return_type == "list[PromptMessage]" %}
    # Generate a multi-message conversation
    messages = [
        Message(f"""{{ prompt_instruction|default('Analyze and process the following:') }}

{% for param in params %}{% if not param.get('optional', False) %}<{{ param.name }}>
{{ '{' }}{{ param.name }}{{ '}' }}
</{{ param.name }}>

{% endif %}{% endfor %}"""),
        # TODO: Add additional messages for conversation context
    ]

    return messages
{% endif %}
```

---

### Phase 3: Type Support Enhancements

#### 3.1 Add PromptResult to Valid Return Types

**File**: `src/fips_agents_cli/tools/generators.py`

Since prompts can return various types, we should allow flexibility:

```python
# Add to valid_return_types for prompts
PROMPT_RETURN_TYPES = [
    "str",
    "PromptMessage",
    "PromptResult",
    "list[PromptMessage]",
    "list[PromptMessage | str]",
]
```

---

### Phase 4: Template Examples

**File**: `src/prompts/analysis.py`

#### 4.1 Add Async Prompt Example

```python
@mcp.prompt
async def fetch_and_analyze(
    data_source: str = Field(description="URL or path to data source"),
    ctx: Context,
) -> str:
    """
    Fetch data asynchronously and generate analysis prompt.

    Demonstrates async prompts with Context access.
    """
    # Simulate async data fetching
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(data_source) as response:
            data = await response.text()

    return f"""Analyze the following data fetched from {data_source}:

<data>
{data[:500]}...
</data>

Request ID: {ctx.request_id}

Provide:
1. Key insights
2. Data quality assessment
3. Recommendations"""
```

#### 4.2 Add PromptMessage Example

```python
from fastmcp.prompts.prompt import Message, PromptMessage, TextContent

@mcp.prompt
def structured_request(
    task: str = Field(description="Task description"),
    format: str = Field(default="json", description="Output format"),
) -> PromptMessage:
    """
    Generate a structured request message.

    Demonstrates PromptMessage return type.
    """
    content = f"""Please perform the following task: {task}

Return the result in {format} format with proper structure and validation."""

    return PromptMessage(
        role="user",
        content=TextContent(type="text", text=content)
    )
```

#### 4.3 Add Multi-Message Example

```python
@mcp.prompt
def conversation_starter(
    topic: str = Field(description="Conversation topic"),
) -> list[PromptMessage]:
    """
    Start a multi-turn conversation.

    Demonstrates list[PromptMessage] return type for conversations.
    """
    return [
        Message(f"Let's discuss {topic}. What are your initial thoughts?"),
        Message("I find this topic fascinating. Let me share some context...", role="assistant"),
        Message("Based on that context, what specific aspects should we explore?"),
    ]
```

#### 4.4 Add Decorator Arguments Example

```python
@mcp.prompt(
    name="advanced_analysis",
    title="Advanced Data Analysis",
    description="Performs comprehensive analysis with multiple perspectives",
    tags={"analysis", "advanced", "multi-perspective"},
    meta={"version": "2.0", "author": "data-team", "complexity": "high"}
)
def complex_analysis(
    data: dict[str, str] = Field(description="Data to analyze"),
    perspectives: list[str] = Field(
        default=["technical", "business"],
        description="Analysis perspectives"
    ),
) -> str:
    """
    Complex analysis prompt with full decorator configuration.

    Demonstrates all decorator arguments.
    """
    perspectives_str = ", ".join(perspectives)
    return f"""Perform a comprehensive analysis from these perspectives: {perspectives_str}

Data:
{data}

Provide:
1. Analysis from each perspective
2. Cross-perspective insights
3. Synthesis and recommendations"""
```

---

### Phase 5: Documentation Updates

#### 5.1 Update CLAUDE.md

**File**: `CLAUDE.md`

Add new section after existing prompt documentation:

```markdown
## Prompt Generation Options (FastMCP 2.x)

### Return Types

Prompts can return different types based on use case:

**`str` (default)**: Simple string prompt
```python
@mcp.prompt
def simple_prompt(query: str) -> str:
    return f"Please answer: {query}"
```

**`PromptMessage`**: Structured message with role
```python
from fastmcp.prompts.prompt import PromptMessage, TextContent

@mcp.prompt
def structured_prompt(query: str) -> PromptMessage:
    return PromptMessage(
        role="user",
        content=TextContent(type="text", text=f"Please answer: {query}")
    )
```

**`list[PromptMessage]`**: Multi-turn conversation
```python
from fastmcp.prompts.prompt import Message

@mcp.prompt
def conversation(topic: str) -> list[PromptMessage]:
    return [
        Message(f"Let's discuss {topic}"),
        Message("That's interesting!", role="assistant"),
        Message("What do you think about...?")
    ]
```

### Async Prompts

Use async prompts when performing I/O operations:

```python
@mcp.prompt
async def fetch_prompt(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.text()
    return f"Analyze this data: {data}"
```

Generate with: `fips-agents generate prompt fetch_data --async`

### Context Access

Access MCP context for request metadata and features:

```python
from fastmcp import Context

@mcp.prompt
def tracked_prompt(query: str, ctx: Context) -> str:
    return f"Query: {query}\nRequest ID: {ctx.request_id}"
```

Generate with: `fips-agents generate prompt my_prompt --with-context`

### Decorator Arguments

Customize prompt metadata:

```python
@mcp.prompt(
    name="custom_name",
    title="Human Readable Title",
    description="Custom description",
    tags={"category", "type"},
    enabled=True,
    meta={"version": "1.0", "author": "team"}
)
def my_prompt() -> str:
    return "..."
```

Generate with:
```bash
fips-agents generate prompt my_prompt \\
    --prompt-name "custom_name" \\
    --title "Human Readable Title" \\
    --tags "category,type" \\
    --meta '{"version": "1.0"}'
```
```

#### 5.2 Update README.md

**File**: `README.md`

Update prompt generation examples:

```markdown
### Generating Prompts

#### Basic Prompt
```bash
fips-agents generate prompt summarize_text \\
    --description "Summarize text content"
```

#### Async Prompt with Context
```bash
fips-agents generate prompt fetch_and_analyze \\
    --async \\
    --with-context \\
    --return-type PromptMessage \\
    --description "Fetch and analyze data asynchronously"
```

#### Prompt with Parameters
```bash
# Create params.json
cat > params.json << 'EOF'
[
  {
    "name": "data",
    "type": "dict[str, str]",
    "description": "Data to analyze",
    "required": true
  },
  {
    "name": "analysis_type",
    "type": "str",
    "description": "Type of analysis",
    "default": "\"summary\"",
    "required": false
  }
]
EOF

fips-agents generate prompt analyze_data \\
    --params params.json \\
    --with-schema \\
    --return-type "list[PromptMessage]"
```

#### Advanced Prompt with Metadata
```bash
fips-agents generate prompt report_generator \\
    --async \\
    --with-context \\
    --prompt-name "generate_report" \\
    --title "Report Generator" \\
    --tags "reporting,analysis,business" \\
    --meta '{"version": "2.0", "author": "data-team"}' \\
    --description "Generate comprehensive business reports"
```
```

---

### Phase 6: Testing Strategy

#### 6.1 Unit Tests

**File**: `tests/test_generate_prompts.py` (new file)

```python
"""Tests for prompt generation."""

import json
from pathlib import Path
from click.testing import CliRunner
from fips_agents_cli.cli import cli


class TestPromptGeneration:
    """Tests for generating prompt components."""

    def test_generate_basic_str_prompt(self, tmp_path, mock_project):
        """Test generating basic string prompt."""
        result = CliRunner().invoke(
            cli,
            ["generate", "prompt", "test_prompt",
             "--description", "Test prompt"],
            cwd=str(mock_project)
        )

        assert result.exit_code == 0

        prompt_file = mock_project / "src/prompts/test_prompt.py"
        content = prompt_file.read_text()

        assert "def test_prompt(" in content
        assert "-> str:" in content
        assert '@mcp.prompt' in content
        assert 'return f"""' in content

    def test_generate_async_prompt(self, tmp_path, mock_project):
        """Test generating async prompt."""
        result = CliRunner().invoke(
            cli,
            ["generate", "prompt", "async_prompt", "--async"],
            cwd=str(mock_project)
        )

        assert result.exit_code == 0

        prompt_file = mock_project / "src/prompts/async_prompt.py"
        content = prompt_file.read_text()

        assert "async def async_prompt(" in content

    def test_generate_prompt_with_context(self, tmp_path, mock_project):
        """Test generating prompt with Context parameter."""
        result = CliRunner().invoke(
            cli,
            ["generate", "prompt", "ctx_prompt", "--with-context"],
            cwd=str(mock_project)
        )

        assert result.exit_code == 0

        prompt_file = mock_project / "src/prompts/ctx_prompt.py"
        content = prompt_file.read_text()

        assert "from fastmcp import Context" in content
        assert "ctx: Context" in content

    def test_generate_prompt_message_type(self, tmp_path, mock_project):
        """Test generating PromptMessage return type."""
        result = CliRunner().invoke(
            cli,
            ["generate", "prompt", "msg_prompt",
             "--return-type", "PromptMessage"],
            cwd=str(mock_project)
        )

        assert result.exit_code == 0

        prompt_file = mock_project / "src/prompts/msg_prompt.py"
        content = prompt_file.read_text()

        assert "from fastmcp.prompts.prompt import" in content
        assert "-> PromptMessage:" in content
        assert "return PromptMessage(" in content

    def test_generate_list_prompt(self, tmp_path, mock_project):
        """Test generating list[PromptMessage] return type."""
        result = CliRunner().invoke(
            cli,
            ["generate", "prompt", "list_prompt",
             "--return-type", "list[PromptMessage]"],
            cwd=str(mock_project)
        )

        assert result.exit_code == 0

        prompt_file = mock_project / "src/prompts/list_prompt.py"
        content = prompt_file.read_text()

        assert "-> list[PromptMessage]:" in content
        assert "messages = [" in content
        assert "Message(" in content

    def test_generate_with_decorator_args(self, tmp_path, mock_project):
        """Test generating prompt with decorator arguments."""
        result = CliRunner().invoke(
            cli,
            ["generate", "prompt", "advanced_prompt",
             "--prompt-name", "custom_name",
             "--title", "Custom Title",
             "--tags", "cat1,cat2",
             "--meta", '{"version": "1.0"}'],
            cwd=str(mock_project)
        )

        assert result.exit_code == 0

        prompt_file = mock_project / "src/prompts/advanced_prompt.py"
        content = prompt_file.read_text()

        assert '@mcp.prompt(' in content
        assert 'name="custom_name"' in content
        assert 'title="Custom Title"' in content
        assert '"cat1", "cat2"' in content
        assert 'meta=' in content

    def test_generate_disabled_prompt(self, tmp_path, mock_project):
        """Test generating disabled prompt."""
        result = CliRunner().invoke(
            cli,
            ["generate", "prompt", "disabled_prompt", "--disabled"],
            cwd=str(mock_project)
        )

        assert result.exit_code == 0

        prompt_file = mock_project / "src/prompts/disabled_prompt.py"
        content = prompt_file.read_text()

        assert "enabled=False" in content
```

#### 6.2 Integration Tests

Test prompt generation end-to-end:

```python
def test_prompt_integration(self, tmp_path, mock_project):
    """Test full prompt generation workflow."""
    # Create params file
    params = [
        {
            "name": "query",
            "type": "str",
            "description": "Search query",
            "required": True
        }
    ]
    params_file = tmp_path / "params.json"
    params_file.write_text(json.dumps(params))

    # Generate prompt
    result = CliRunner().invoke(
        cli,
        ["generate", "prompt", "search_prompt",
         "--async",
         "--with-context",
         "--return-type", "PromptMessage",
         "--params", str(params_file),
         "--tags", "search,query"],
        cwd=str(mock_project)
    )

    assert result.exit_code == 0

    # Verify generated code
    prompt_file = mock_project / "src/prompts/search_prompt.py"
    assert prompt_file.exists()

    content = prompt_file.read_text()

    # Verify all features present
    assert "async def search_prompt(" in content
    assert "query: str" in content
    assert "ctx: Context" in content
    assert "-> PromptMessage:" in content
    assert "from fastmcp import Context" in content
    assert "from fastmcp.prompts.prompt import" in content

    # Verify Python syntax is valid
    import ast
    ast.parse(content)  # Should not raise
```

#### 6.3 Template Rendering Tests

```python
def test_template_all_combinations(self):
    """Test template renders correctly with all option combinations."""
    from fips_agents_cli.tools.generators import load_template, render_component

    project_root = Path("/path/to/template")
    template = load_template(project_root, "prompt", "component.py.j2")

    # Test matrix
    combinations = [
        {"async": False, "with_context": False, "return_type": "str"},
        {"async": True, "with_context": False, "return_type": "str"},
        {"async": False, "with_context": True, "return_type": "PromptMessage"},
        {"async": True, "with_context": True, "return_type": "list[PromptMessage]"},
    ]

    for combo in combinations:
        template_vars = {
            "component_name": "test_prompt",
            "description": "Test prompt",
            "params": [],
            **combo
        }

        rendered = render_component(template, template_vars)

        # Verify syntax
        import ast
        ast.parse(rendered)

        # Verify expected patterns
        if combo["async"]:
            assert "async def" in rendered
        else:
            assert "async def" not in rendered

        if combo["with_context"]:
            assert "ctx: Context" in rendered

        assert f"-> {combo['return_type']}:" in rendered
```

---

### Phase 7: Migration Guide

#### 7.1 For Existing Prompts

**File**: `PROMPT_MIGRATION_GUIDE.md` (new)

```markdown
# Migrating Prompts to Enhanced Generation

## Overview

The updated prompt generator now supports:
- Async prompts
- Context parameters
- Multiple return types
- Decorator arguments

## Migration Steps

### Step 1: Identify Prompt Needs

Review your existing prompts and identify:
- Do they perform I/O? → Add `--async`
- Do they need request metadata? → Add `--with-context`
- What do they return? → Set `--return-type`

### Step 2: Re-generate with New Options

**Before:**
```bash
fips-agents generate prompt my_prompt \\
    --description "My prompt"
```

**After:**
```bash
fips-agents generate prompt my_prompt \\
    --async \\
    --with-context \\
    --return-type "PromptMessage" \\
    --description "My prompt" \\
    --tags "category,type"
```

### Step 3: Update Imports

Old prompts may need additional imports:

```python
# Add if using PromptMessage/list types
from fastmcp.prompts.prompt import Message, PromptMessage, TextContent

# Add if using Context
from fastmcp import Context
```

### Step 4: Update Return Statements

Match your return statement to the return type:

**For `str`:** (no change needed)
```python
return f"Prompt text..."
```

**For `PromptMessage`:**
```python
return PromptMessage(
    role="user",
    content=TextContent(type="text", text=f"Prompt text...")
)
```

**For `list[PromptMessage]`:**
```python
return [
    Message("First message"),
    Message("Second message", role="assistant"),
]
```

## Examples

### Migrating to Async

**Before:**
```python
@mcp.prompt
def fetch_data(url: str) -> str:
    # This should be async!
    data = requests.get(url).text
    return f"Analyze: {data}"
```

**After:**
```python
@mcp.prompt
async def fetch_data(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.text()
    return f"Analyze: {data}"
```

### Adding Context

**Before:**
```python
@mcp.prompt
def my_prompt(query: str) -> str:
    return f"Query: {query}"
```

**After:**
```python
from fastmcp import Context

@mcp.prompt
def my_prompt(query: str, ctx: Context) -> str:
    return f"Query: {query}\nRequest: {ctx.request_id}"
```
```

---

### Phase 8: Implementation Checklist

#### 8.1 CLI Changes
- [ ] Add `--async/--sync` option to prompt command
- [ ] Add `--with-context` flag
- [ ] Add `--return-type` choice option
- [ ] Add `--prompt-name` option
- [ ] Add `--title` option
- [ ] Add `--tags` option
- [ ] Add `--disabled` flag
- [ ] Add `--meta` option (JSON string)
- [ ] Parse tags from comma-separated string
- [ ] Parse and validate meta JSON
- [ ] Update template_vars to include all new options
- [ ] Update command help text and examples

#### 8.2 Template Changes
- [ ] Add conditional imports for PromptMessage/Context
- [ ] Support decorator arguments (name, title, tags, enabled, meta)
- [ ] Support `async def` when async flag set
- [ ] Add Context parameter when with_context flag set
- [ ] Generate appropriate return statements for each return_type
- [ ] Add Message() helper examples for list types
- [ ] Update docstring to document Context when present
- [ ] Test all template combinations render valid Python

#### 8.3 Examples
- [ ] Add async prompt example
- [ ] Add Context access example
- [ ] Add PromptMessage return type example
- [ ] Add list[PromptMessage] conversation example
- [ ] Add decorator arguments example
- [ ] Add combined async + Context + parameters example

#### 8.4 Documentation
- [ ] Update CLAUDE.md with return types section
- [ ] Update CLAUDE.md with async prompts section
- [ ] Update CLAUDE.md with Context access section
- [ ] Update CLAUDE.md with decorator arguments section
- [ ] Update README.md with new CLI examples
- [ ] Create PROMPT_MIGRATION_GUIDE.md
- [ ] Update existing docs to reflect new capabilities

#### 8.5 Testing
- [ ] Write unit tests for all CLI options
- [ ] Write tests for each return type
- [ ] Write tests for async prompts
- [ ] Write tests for Context parameter
- [ ] Write tests for decorator arguments
- [ ] Write integration test for all features combined
- [ ] Write template rendering tests for all combinations
- [ ] Verify generated code has valid Python syntax
- [ ] Verify generated code works with FastMCP

#### 8.6 Validation
- [ ] Test manual generation with each option
- [ ] Test generated prompts in actual MCP server
- [ ] Verify prompts work with MCP clients
- [ ] Verify async prompts execute correctly
- [ ] Verify Context provides expected data
- [ ] Verify decorator arguments appear in MCP protocol

---

## Risk Assessment

### Low Risk
- Adding new CLI options (backward compatible)
- Adding template examples
- Documentation updates

### Medium Risk
- Template changes (affects code generation)
- Return type handling (requires correct imports/syntax)
- Decorator argument formatting (Jinja escaping)

### High Risk
- None identified (all changes are additive)

### Mitigation Strategies

1. **Comprehensive Testing**: Test all option combinations
2. **Syntax Validation**: AST parse all generated code
3. **Manual Verification**: Test generated prompts in real MCP server
4. **Gradual Rollout**: Update template, test, then update CLI
5. **Documentation First**: Document before implementing
6. **Backward Compatibility**: Existing prompts continue working

---

## Success Criteria

- [ ] All new CLI options work correctly
- [ ] Generated code has valid Python syntax
- [ ] Generated prompts work with FastMCP
- [ ] All return types generate correct code
- [ ] Async prompts execute without errors
- [ ] Context parameter provides expected data
- [ ] Decorator arguments appear in MCP protocol
- [ ] All tests pass
- [ ] Documentation complete and accurate
- [ ] Examples demonstrate all features

---

## Timeline Estimate

- **Phase 1 (CLI)**: 2-3 hours
- **Phase 2 (Template)**: 3-4 hours
- **Phase 3 (Type Support)**: 1 hour
- **Phase 4 (Examples)**: 2 hours
- **Phase 5 (Documentation)**: 2 hours
- **Phase 6 (Testing)**: 3-4 hours
- **Phase 7 (Migration Guide)**: 1 hour
- **Phase 8 (Validation)**: 2 hours

**Total**: 16-21 hours

---

## Conclusion

This plan comprehensively addresses all gaps between the current prompt generator and FastMCP's documented capabilities. Implementation follows proven patterns from the tool generator while adding prompt-specific features. All changes are backward compatible and additive.
