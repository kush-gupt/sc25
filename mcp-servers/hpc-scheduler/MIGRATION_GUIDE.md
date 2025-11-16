# Migrating Prompts to FastMCP 2.9.0+ Patterns

If you have existing prompts generated with older templates, follow these steps:

## Step 1: Update Type Annotations

**Before**:
```python
from typing import Annotated

@mcp.prompt()
def my_prompt(
    data: Annotated[dict, Field(description="...")],
) -> str:
```

**After**:
```python
@mcp.prompt
def my_prompt(
    data: dict[str, str] = Field(description="..."),
) -> str:
```

**Changes**:
1. Add type parameters to dict: `dict` → `dict[str, str]` or `dict[str, Any]`
2. Remove `Annotated[]` wrapper
3. Use `Field()` directly with equals sign
4. Remove `()` from `@mcp.prompt` decorator

## Step 2: Update Optional Parameters

**Before**:
```python
    format: Annotated[
        str | None,
        Field(description="...", default="json"),
    ] = "json",
```

**After**:
```python
    format: str = Field(
        default="json",
        description="..."
    ),
```

**Changes**:
1. Move default into Field()
2. Remove redundant `= "json"` after annotation
3. Type becomes just `str` (not `str | None`) when default is provided

## Step 3: Update Imports

Remove unused imports:
- `from typing import Annotated` (if not used elsewhere)
- `from typing import Literal` (if not used)

## Step 4: Test Changes

```bash
# Run tests
pytest tests/prompts/test_your_prompt.py -v

# Test locally with cmcp
make test-local

# Deploy and verify
make deploy
```

## Step 5: Verify MCP Arguments

```bash
# Connect to your server
cmcp 'your-server-url' prompts/list

# Should show arguments array populated:
# "arguments": [
#   {"name": "data", "description": "...", "required": true},
#   ...
# ]
```

## Example: Complete Before/After

### Before (Old Pattern)
```python
from typing import Annotated
from pydantic import Field
from core.app import mcp


@mcp.prompt()
def weather_report(
    weather_data: Annotated[
        dict,
        Field(description="Weather data as a dictionary"),
    ],
    output_format: str = "narrative",
) -> str:
    """Generate weather report."""
    return f"..."
```

### After (New Pattern)
```python
from pydantic import Field
from core.app import mcp


@mcp.prompt
def weather_report(
    weather_data: dict[str, str] = Field(
        description="Weather data as a dictionary with string keys and values"
    ),
    output_format: str = Field(
        default="narrative",
        description="Desired output format: 'narrative', 'structured', or 'brief'"
    ),
) -> str:
    """Generate weather report."""
    return f"..."
```

## Automated Refactoring

Consider using `ruff` or `black` for consistent formatting:

```bash
# Format updated prompts
ruff format src/prompts/

# Check for issues
ruff check src/prompts/
```
