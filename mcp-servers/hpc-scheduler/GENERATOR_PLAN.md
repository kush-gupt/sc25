# Generator System Planning Document

## Table of Contents
1. [Vision & Goals](#vision--goals)
2. [Command Structure](#command-structure)
3. [Component Self-Registration Pattern](#component-self-registration-pattern)
4. [Generator Workflow](#generator-workflow)
5. [Jinja2 Template Patterns](#jinja2-template-patterns)
6. [File Organization](#file-organization)
7. [Generated Code Examples](#generated-code-examples)

---

## Vision & Goals

The generator system enables developers to scaffold new MCP components (tools, resources, prompts, middleware) with consistent structure, best practices, and comprehensive tests. Key goals:

- **Consistency**: All generated components follow FastMCP 2.x best practices
- **Productivity**: Reduce boilerplate, focus on business logic
- **Quality**: Generated code includes tests, documentation, and error handling
- **Flexibility**: Templates are per-project customizable, not baked into CLI
- **Education**: Generated code serves as working examples

### Design Philosophy

1. **Templates live in projects**, not in the CLI tool
2. **Self-registration via decorators** - no manual server.py updates
3. **Dynamic loading at startup** - components are discovered automatically
4. **Hot-reload support** - changes reflect immediately in dev mode

---

## Command Structure

### General Pattern

```bash
fips-agents generate <component-type> <name> [flags]
```

### Component Types

#### 1. Tool Generation

```bash
fips-agents generate tool <name> [flags]

# Examples:
fips-agents generate tool fetch-user
fips-agents generate tool calculate-metrics --async --with-context --with-auth
fips-agents generate tool validate-email --sync
```

**Common Flags:**
- `--async` / `--sync` - Generate async or sync function (default: async)
- `--with-context` - Include FastMCP Context parameter for logging
- `--with-auth` - Include authentication decorator example
- `--description "..."` - Tool description (interactive prompt if not provided)

**Tool-Specific Flags:**
- `--read-only` - Mark as read-only operation (idempotent hint)
- `--open-world` - Mark as open-world operation (can interact with external systems)

#### 2. Resource Generation

```bash
fips-agents generate resource <name> [flags]

# Examples:
fips-agents generate resource config
fips-agents generate resource user-profile --async
fips-agents generate resource system-status
```

**Resource-Specific Flags:**
- `--uri <uri>` - Custom resource URI (default: `resource://<name>`)
- `--mime-type <type>` - MIME type for the resource (default: text/plain)

#### 3. Prompt Generation

```bash
fips-agents generate prompt <name> [flags]

# Examples:
fips-agents generate prompt analyze-code
fips-agents generate prompt summarize-document --with-schema
```

**Prompt-Specific Flags:**
- `--with-schema` - Generate JSON schema for structured output
- `--params "param1:str,param2:int"` - Define parameters (interactive if not provided)

#### 4. Middleware Generation

```bash
fips-agents generate middleware <name> [flags]

# Examples:
fips-agents generate middleware rate-limiter
fips-agents generate middleware audit-logger --async
fips-agents generate middleware custom-auth
```

**Middleware-Specific Flags:**
- `--hook-type <type>` - Middleware hook point (before_tool, after_tool, on_error)

---

## Component Self-Registration Pattern

### How It Works

FastMCP 2.x uses **decorator-based registration**. When you annotate a function with `@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()`, or apply middleware, the component **automatically registers itself** when the module is imported.

```python
# In src/core/app.py - Create the FastMCP instance
from fastmcp import FastMCP
mcp = FastMCP("my-server")

# In src/tools/my_tool.py - Import the mcp instance and use decorator
from core.app import mcp

@mcp.tool()  # <-- Registration happens here when module loads
async def my_tool(param: str) -> str:
    return f"Result: {param}"
```

### Dynamic Loading via loaders.py

The `src/core/loaders.py` module discovers and imports all components at startup:

```python
def load_tools(mcp: FastMCP, tools_dir: Path) -> int:
    """Load all .py files from tools/ directory."""
    for py_file in tools_dir.glob("*.py"):
        if py_file.name != "__init__.py":
            importlib.import_module(f"tools.{py_file.stem}")
    # Components are now registered via decorators
```

### Key Insight: No Manual Registration Needed

**You do NOT need to modify `server.py` to add new components.**

```python
# ❌ OLD WAY (pre-FastMCP 2.x):
# server.py
mcp.tool(my_tool)      # Manual registration
mcp.resource(my_resource)

# ✅ NEW WAY (FastMCP 2.x):
# Just import the module - decorators handle registration
# loaders.py
importlib.import_module("tools.my_tool")  # @mcp.tool decorator registers it
```

### Hot-Reload Support

The loader includes hot-reload capability for development:

```python
class _ReloadHandler:
    def on_any_event(self, event):
        # Reload changed modules
        importlib.reload(sys.modules["tools.my_tool"])
        # Decorators re-register the components
```

---

## Generator Workflow

### Phase 1: Validation

1. **Project Structure Check**: Verify we're in an MCP server project
2. **Name Validation**: Ensure component name is valid Python identifier
3. **Collision Check**: Check if component already exists
4. **Template Availability**: Verify generator templates exist

### Phase 2: Interactive Prompts (if needed)

If flags are not provided, interactively collect:
- Component description
- Parameters and their types
- Optional features (async, auth, context)

### Phase 3: Generation

1. **Load Jinja2 Template**: Read `component.py.j2` from `.fips-agents-cli/generators/<type>/`
2. **Render Component**: Apply variables to template
3. **Write Component File**: Save to appropriate directory (tools/, resources/, prompts/, middleware/)
4. **Generate Test**: Render and write test file to `tests/<type>/`

### Phase 4: Post-Generation

1. **Verify Syntax**: Run basic Python syntax check
2. **Success Message**: Display file paths and next steps
3. **Test Instructions**: Show how to run tests

---

## Jinja2 Template Patterns

### Common Template Variables

All templates have access to these variables:

```python
{
    "component_name": "my_tool",           # Snake_case function name
    "component_class_name": "MyTool",      # PascalCase if needed
    "description": "Tool description",     # Human-readable description
    "async": True,                         # Async vs sync
    "with_context": True,                  # Include Context parameter
    "with_auth": False,                    # Include auth decorator
    "project_name": "my-mcp-server",       # Project name for imports
    "params": [                            # Parameter definitions
        {
            "name": "query",
            "type": "str",
            "description": "Search query",
            "required": True,
            "default": None
        }
    ]
}
```

### Template Structure Guidelines

#### 1. Conditional Imports

```jinja2
from typing import Annotated
from core.app import mcp
{% if async %}from fastmcp import Context{% endif %}
{% if with_auth %}from core.auth import requires_scopes{% endif %}
```

#### 2. Decorator Application

```jinja2
@mcp.tool(
    annotations={
        "readOnlyHint": {{ read_only|lower }},
        "idempotentHint": {{ idempotent|lower }},
    }
)
{% if with_auth %}
@requires_scopes({{ required_scopes|tojson }})
{% endif %}
```

#### 3. Function Signature

```jinja2
{% if async %}async {% endif %}def {{ component_name }}(
    {% for param in params %}
    {{ param.name }}: Annotated[{{ param.type }}, "{{ param.description }}"]{% if param.default %} = {{ param.default }}{% endif %},
    {% endfor %}
    {% if with_context %}ctx: Context = None,{% endif %}
) -> {{ return_type }}:
```

#### 4. Documentation Strings

```jinja2
    """{{ description }}

    Args:
    {% for param in params %}
        {{ param.name }}: {{ param.description }}
    {% endfor %}
    {% if with_context %}
        ctx: FastMCP context for logging and capabilities
    {% endif %}

    Returns:
        {{ return_description }}

    Raises:
        ToolError: If validation fails
    """
```

#### 5. Implementation Placeholder

```jinja2
    {% if with_context and async %}
    await ctx.info(f"Executing {{ component_name }}")
    {% endif %}

    # TODO: Implement business logic
    {% if async %}
    # Example async operation
    # result = await fetch_data(param)
    {% else %}
    # Example sync operation
    # result = process_data(param)
    {% endif %}

    return "result"
```

### Comment Conventions for User Guidance

Templates should include instructional comments:

```python
# TODO: Implement business logic
# Remove this placeholder and add your implementation

# EXAMPLE: Async HTTP request
# async with httpx.AsyncClient() as client:
#     response = await client.get(url)
#     return response.json()

# EXAMPLE: Database query
# with get_db_connection() as conn:
#     result = conn.execute(query)
#     return result.fetchall()
```

---

## File Organization

### Project Structure with Generators

```
my-mcp-server/
├── .fips-agents-cli/
│   ├── README.md                         # Generator system docs
│   └── generators/
│       ├── tool/
│       │   ├── component.py.j2           # Tool implementation template
│       │   ├── test.py.j2                # Tool test template
│       │   └── README.md                 # Tool generator docs
│       ├── resource/
│       │   ├── component.py.j2
│       │   ├── test.py.j2
│       │   └── README.md
│       ├── prompt/
│       │   ├── component.py.j2
│       │   ├── test.py.j2
│       │   └── README.md
│       └── middleware/
│           ├── component.py.j2
│           ├── test.py.j2
│           └── README.md
├── src/
│   ├── core/
│   │   ├── app.py                        # FastMCP instance
│   │   ├── loaders.py                    # Dynamic loading
│   │   └── server.py                     # Server bootstrap
│   ├── tools/                            # Generated tools go here
│   ├── resources/                        # Generated resources go here
│   ├── prompts/                          # Generated prompts go here
│   └── middleware/                       # Generated middleware go here
└── tests/
    ├── tools/                            # Generated tool tests
    ├── resources/                        # Generated resource tests
    ├── prompts/                          # Generated prompt tests
    └── middleware/                       # Generated middleware tests
```

### Naming Conventions

**Component Files:**
- Snake_case: `fetch_user.py`, `calculate_metrics.py`
- Match function name: File `my_tool.py` contains function `my_tool()`

**Test Files:**
- Prefix with `test_`: `test_fetch_user.py`, `test_calculate_metrics.py`
- Test class name: `TestFetchUser`, `TestCalculateMetrics`

---

## Generated Code Examples

### Example 1: Simple Sync Tool

**Command:**
```bash
fips-agents generate tool echo --sync --description "Echo a message back"
```

**Generated: `src/tools/echo.py`**
```python
from typing import Annotated
from core.app import mcp

@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
    }
)
def echo(
    message: Annotated[str, "The message to echo"],
) -> str:
    """Echo a message back.

    Args:
        message: The message to echo

    Returns:
        The echoed message
    """
    return message
```

**Generated: `tests/tools/test_echo.py`**
```python
import pytest
from src.tools.echo import echo

def test_echo_basic():
    """Test basic echo functionality."""
    result = echo(message="Hello")
    assert result == "Hello"

def test_echo_empty():
    """Test echo with empty string."""
    result = echo(message="")
    assert result == ""
```

---

### Example 2: Async Tool with Context and Auth

**Command:**
```bash
fips-agents generate tool fetch-user \
  --async \
  --with-context \
  --with-auth \
  --description "Fetch user information by ID"
```

**Generated: `src/tools/fetch_user.py`**
```python
from typing import Annotated
from pydantic import Field
from fastmcp import Context
from fastmcp.exceptions import ToolError
from core.app import mcp
from core.auth import requires_scopes

@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
    }
)
@requires_scopes("read:users")
async def fetch_user(
    user_id: Annotated[str, Field(description="User ID to fetch", min_length=1)],
    ctx: Context = None,
) -> str:
    """Fetch user information by ID.

    Args:
        user_id: User ID to fetch
        ctx: FastMCP context for logging and capabilities

    Returns:
        User information as JSON string

    Raises:
        ToolError: If user not found or validation fails
    """
    await ctx.info(f"Fetching user: {user_id}")

    # TODO: Implement business logic
    # Example async operation:
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(f"https://api.example.com/users/{user_id}")
    #     if response.status_code == 404:
    #         raise ToolError(f"User {user_id} not found")
    #     return response.json()

    return f'{{"id": "{user_id}", "name": "John Doe"}}'
```

**Generated: `tests/tools/test_fetch_user.py`**
```python
import pytest
from unittest.mock import AsyncMock, patch
from src.tools.fetch_user import fetch_user

@pytest.mark.asyncio
async def test_fetch_user_basic():
    """Test basic user fetch."""
    ctx = AsyncMock()
    result = await fetch_user(user_id="123", ctx=ctx)
    assert "123" in result
    ctx.info.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_user_empty_id():
    """Test fetch with empty user ID."""
    from pydantic import ValidationError
    ctx = AsyncMock()
    with pytest.raises(ValidationError):
        await fetch_user(user_id="", ctx=ctx)
```

---

### Example 3: Resource

**Command:**
```bash
fips-agents generate resource config --uri "resource://app-config"
```

**Generated: `src/resources/config.py`**
```python
from core.app import mcp

@mcp.resource("resource://app-config", name="config")
async def config() -> str:
    """Application configuration resource.

    Returns:
        Configuration data as string
    """
    # TODO: Implement resource retrieval
    # Example: Load from file or database
    # config_data = await load_config()
    # return json.dumps(config_data)

    return '{"setting": "value"}'
```

**Generated: `tests/resources/test_config.py`**
```python
import pytest
from src.resources.config import config

@pytest.mark.asyncio
async def test_config_returns_json():
    """Test config resource returns valid JSON."""
    result = await config()
    import json
    data = json.loads(result)
    assert isinstance(data, dict)
```

---

### Example 4: Prompt with Schema

**Command:**
```bash
fips-agents generate prompt analyze-code --with-schema
```

**Generated: `src/prompts/analyze_code.py`**
```python
from typing import Annotated
from pydantic import Field
from core.app import mcp

@mcp.prompt()
def analyze_code(
    code: Annotated[str, Field(description="Code to analyze")],
    language: Annotated[str, Field(description="Programming language")] = "python",
) -> str:
    """Analyze code for issues and improvements.

    Args:
        code: The code to analyze
        language: Programming language of the code

    Returns:
        Formatted prompt for code analysis with JSON schema
    """
    return f"""Analyze the following {language} code:

<code>
{code}
</code>

Identify:
1. Potential bugs or errors
2. Performance issues
3. Security vulnerabilities
4. Code quality improvements
5. Best practice violations

Return as JSON:
{{
  "issues": [
    {{
      "type": "bug|performance|security|quality",
      "severity": "high|medium|low",
      "line": <line_number>,
      "description": "Issue description",
      "suggestion": "How to fix"
    }}
  ],
  "summary": "Overall code quality assessment",
  "score": <0-100>
}}"""
```

**Generated: `tests/prompts/test_analyze_code.py`**
```python
import pytest
from src.prompts.analyze_code import analyze_code

def test_analyze_code_basic():
    """Test basic code analysis prompt."""
    code = "def foo():\n    pass"
    result = analyze_code(code=code, language="python")
    assert "python" in result
    assert code in result
    assert "JSON" in result

def test_analyze_code_default_language():
    """Test default language parameter."""
    code = "function test() {}"
    result = analyze_code(code=code)
    assert "python" in result  # Default language
```

---

### Example 5: Middleware (Logging)

**Command:**
```bash
fips-agents generate middleware request-logger --async
```

**Generated: `src/middleware/request_logger.py`**
```python
from typing import Any, Callable
from fastmcp import Context
from core.app import mcp
from core.logging import get_logger

log = get_logger("request_logger")

@mcp.middleware()
async def request_logger(
    ctx: Context,
    next_handler: Callable,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Log all tool invocations.

    This middleware logs request details before and after execution.

    Args:
        ctx: FastMCP context
        next_handler: Next handler in the chain
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Result from next handler
    """
    tool_name = ctx.request.tool_name if hasattr(ctx, 'request') else 'unknown'
    log.info(f"Tool invoked: {tool_name}")

    try:
        result = await next_handler(*args, **kwargs)
        log.info(f"Tool completed: {tool_name}")
        return result
    except Exception as e:
        log.error(f"Tool failed: {tool_name} - {e}")
        raise
```

**Generated: `tests/middleware/test_request_logger.py`**
```python
import pytest
from unittest.mock import AsyncMock
from src.middleware.request_logger import request_logger

@pytest.mark.asyncio
async def test_request_logger_success():
    """Test middleware logs successful requests."""
    ctx = AsyncMock()
    ctx.request.tool_name = "test_tool"

    next_handler = AsyncMock(return_value="result")

    result = await request_logger(ctx, next_handler)

    assert result == "result"
    next_handler.assert_called_once()

@pytest.mark.asyncio
async def test_request_logger_error():
    """Test middleware logs errors."""
    ctx = AsyncMock()
    ctx.request.tool_name = "test_tool"

    next_handler = AsyncMock(side_effect=ValueError("Test error"))

    with pytest.raises(ValueError):
        await request_logger(ctx, next_handler)
```

---

### Example 6: Middleware (Auth)

**Command:**
```bash
fips-agents generate middleware auth-checker --async
```

**Generated: `src/middleware/auth_checker.py`**
```python
from typing import Any, Callable
from fastmcp import Context
from fastmcp.exceptions import ToolError
from core.app import mcp
from core.logging import get_logger

log = get_logger("auth_checker")

@mcp.middleware()
async def auth_checker(
    ctx: Context,
    next_handler: Callable,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Check authentication before tool execution.

    This middleware verifies authentication tokens and permissions.

    Args:
        ctx: FastMCP context
        next_handler: Next handler in the chain
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Result from next handler

    Raises:
        ToolError: If authentication fails
    """
    # TODO: Implement authentication check
    # Example:
    # auth_token = ctx.request.headers.get("Authorization")
    # if not auth_token or not verify_token(auth_token):
    #     raise ToolError("Authentication required")

    # For now, just pass through
    log.debug("Auth check passed")
    return await next_handler(*args, **kwargs)
```

---

## Implementation Notes

### Phase 1: CLI Command Implementation

The `fips-agents generate` command will:

1. **Load Project Context**: Detect project root, read pyproject.toml
2. **Validate Template Availability**: Check `.fips-agents-cli/generators/` exists
3. **Process Flags**: Parse command-line flags or prompt interactively
4. **Render Templates**: Use Jinja2 to generate code
5. **Write Files**: Create component and test files
6. **Report Success**: Show file paths and next steps

### Phase 2: Template Customization

Projects can customize templates by:

1. **Editing existing templates** in `.fips-agents-cli/generators/`
2. **Adding new templates** for custom component types
3. **Modifying variables** and conditional logic
4. **Sharing templates** across projects via git

### Testing Strategy

- Generated code must be syntactically valid Python
- Generated tests must be runnable with pytest
- CLI includes `--dry-run` flag to preview without writing files
- CLI includes `--validate` flag to check generated code syntax

---

## Conclusion

This generator system provides a consistent, flexible foundation for scaffolding MCP components. By keeping templates in projects (not the CLI), developers can customize generation to match their specific needs while maintaining the benefits of automation and consistency.

The decorator-based self-registration pattern eliminates manual server configuration, making component addition as simple as creating a file in the appropriate directory.
