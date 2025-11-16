# FastMCP 2.x Prompt Template Update Plan

## Executive Summary

Update the MCP server template and fips-agents-cli tool to support FastMCP 2.9.0+ argument handling patterns, particularly for prompts. The current template generates code that doesn't expose prompt arguments properly because it uses bare `dict` types and an overly complex annotation pattern.

## Background

### What We Learned from weather-mcp

When fixing the weather-mcp server, we discovered:

1. **FastMCP requires typed dict parameters**: `dict[str, str]` not bare `dict`
2. **Simplified Field pattern works best**: `param: type = Field(default=..., description=...)`
3. **FastMCP handles JSON conversion automatically**: Clients pass JSON strings, FastMCP converts
4. **Simpler is better**: Complex annotation patterns and auto-generated helper variables cause issues

### Current Issues

#### Template Issues (`.fips-agents-cli/generators/prompt/component.py.j2`)

1. **Unused Import** (Line 3): Conditionally imports `Literal` but never uses it
2. **Missing Type Parameter Support**: Only generates bare types like `dict`, not `dict[str, str]`
3. **Inconsistent Optional Pattern** (Lines 10-13): Mixes annotation and function default
4. **Complex Helper Generation** (Lines 23-24): Auto-generates `*_info` variables only for strings

#### CLI Tool Issues (`fips-agents-cli/src/fips_agents_cli/tools/generators.py`)

1. **Limited valid_types** (Lines 166-178): Doesn't include:
   - `dict[str, str]`
   - `dict[str, Any]`
   - Complex parameterized types
2. **No validation** for type parameters on dict/list types

---

## Implementation Plan

### Phase 1: Update CLI Tool Validation (fips-agents-cli)

**File**: `src/fips_agents_cli/tools/generators.py`

#### 1.1 Expand Valid Types List

**Current** (lines 166-178):
```python
valid_types = [
    "str",
    "int",
    "float",
    "bool",
    "list[str]",
    "list[int]",
    "list[float]",
    "Optional[str]",
    "Optional[int]",
    "Optional[float]",
    "Optional[bool]",
]
```

**Updated**:
```python
valid_types = [
    # Simple types
    "str",
    "int",
    "float",
    "bool",

    # List types (parameterized)
    "list[str]",
    "list[int]",
    "list[float]",
    "list[bool]",

    # Dict types (parameterized - REQUIRED for FastMCP 2.9.0+)
    "dict[str, str]",
    "dict[str, Any]",
    "dict[str, int]",
    "dict[str, float]",
    "dict[str, bool]",

    # Optional simple types
    "str | None",
    "int | None",
    "float | None",
    "bool | None",

    # Optional complex types
    "list[str] | None",
    "list[int] | None",
    "dict[str, str] | None",
    "dict[str, Any] | None",
]
```

**Rationale**:
- Modern Python 3.10+ uses `|` for union types, not `Optional[]`
- FastMCP 2.9.0+ requires parameterized dict types for proper schema generation
- Explicit support for `dict[str, Any]` for flexible JSON data

#### 1.2 Add Type Validation Function

**New function** (insert after `load_params_file`):

```python
def validate_type_annotation(type_str: str) -> tuple[bool, str]:
    """
    Validate that a type annotation is properly formatted for FastMCP.

    Args:
        type_str: Type annotation string (e.g., "dict[str, str]")

    Returns:
        tuple: (is_valid, error_message)

    Examples:
        >>> validate_type_annotation("dict")  # Invalid
        (False, "Bare 'dict' type not allowed. Use dict[str, str] or dict[str, Any]")

        >>> validate_type_annotation("dict[str, str]")  # Valid
        (True, "")
    """
    # Check for bare dict/list without parameters
    if type_str in ["dict", "list"]:
        return (
            False,
            f"Bare '{type_str}' type not allowed. "
            f"Use {type_str}[...] with type parameters for FastMCP 2.9.0+ compatibility"
        )

    # Validate dict types have parameters
    if type_str.startswith("dict[") or type_str.startswith("dict |"):
        if not ("[" in type_str and "]" in type_str):
            return False, "Dict types must include type parameters: dict[key_type, value_type]"

    return True, ""
```

#### 1.3 Update load_params_file Validation

**Add after line 183** (after existing type validation):

```python
        # Validate type formatting for FastMCP compliance
        is_valid, error_msg = validate_type_annotation(param["type"])
        if not is_valid:
            raise ValueError(f"Parameter {i} '{param['name']}': {error_msg}")
```

#### 1.4 Add Type Hint Computation

**Add helper function**:

```python
def compute_type_hint(param: dict[str, Any]) -> str:
    """
    Compute the full type hint for a parameter, handling optional types.

    Args:
        param: Parameter definition dictionary

    Returns:
        Complete type hint string (e.g., "str", "dict[str, str]", "str | None")

    Examples:
        >>> compute_type_hint({"type": "str", "optional": False})
        "str"

        >>> compute_type_hint({"type": "dict[str, str]", "optional": True})
        "dict[str, str] | None"
    """
    base_type = param["type"]
    is_optional = param.get("optional", False) or param.get("required", True) is False

    if is_optional and " | None" not in base_type:
        return f"{base_type} | None"

    return base_type
```

**Update template variables in generate.py**:

In `generate_component_workflow`, after loading params (line 101), add:

```python
# Compute type hints for each parameter
for param in template_vars.get("params", []):
    param["type_hint"] = compute_type_hint(param)
```

---

### Phase 2: Update Jinja Template

**File**: `.fips-agents-cli/generators/prompt/component.py.j2`

#### 2.1 Simplified Imports

**Current** (lines 1-5):
```jinja
"""{{ description }}"""

from typing import Annotated{% if params|selectattr('optional')|list|length > 0 %}, Literal{% endif %}
from pydantic import Field
from core.app import mcp
```

**Updated**:
```jinja
"""{{ description }}"""

from pydantic import Field
from core.app import mcp
```

**Changes**:
- Remove unused `Literal` import
- Remove conditional typing imports (not needed with new pattern)

#### 2.2 Simplified Function Signature

**Current** (lines 8-14):
```jinja
@mcp.prompt()
def {{ component_name }}(
{% if params|length > 0 %}{% for param in params %}    {{ param.name }}: Annotated[
        {{ param.type }}{% if param.optional %} | None{% endif %},
        Field(description="{{ param.description }}"{% if param.default is defined %}, default={{ param.default }}{% endif %}),
    ]{% if param.optional %} = {{ param.default }}{% endif %},
{% endfor %}{% endif %}) -> str:
```

**Updated**:
```jinja
@mcp.prompt
def {{ component_name }}(
{% for param in params %}    {{ param.name }}: {{ param.type_hint }} = Field(
{% if param.default is defined %}        default={{ param.default }},
{% endif %}        description="{{ param.description }}"
    ),
{% endfor %}) -> str:
```

**Changes**:
- Use pre-computed `type_hint` that includes `| None` if optional
- Simplified `Field()` pattern without redundant annotation
- Remove unnecessary `@mcp.prompt()` parentheses (decorator works without)
- Consistent comma placement

#### 2.3 Remove Auto-generated Helper Variables

**Current** (lines 23-24):
```jinja
{% if param.optional %}{% if param.type == 'str' %}{{ param.name }}_info = f"{{ param.name|title }}: {{ '{' }}{{ param.name }}{{ '}' }}\n" if {{ param.name }} else ""
{% endif %}{% endif %}
```

**Remove entirely**. Developers should handle conditional logic naturally in their prompt implementation.

#### 2.4 Updated Prompt Body Template

**Current** (lines 25-44):
```jinja
    return f"""{{ prompt_instruction|default('Analyze and process the following:') }}

{% if params|length > 0 %}{% for param in params %}{% if not param.optional %}<{{ param.name }}>
{{ '{' }}{{ param.name }}{{ '}' }}
</{{ param.name }}>

{% endif %}{% endfor %}{% endif %}{% if with_schema %}Provide:
...
{% endif %}"""
```

**Updated**:
```jinja
    return f"""{{ prompt_instruction|default('Analyze and process the following:') }}

{% for param in params %}{% if not param.get('optional', False) %}<{{ param.name }}>
{{ '{' }}{{ param.name }}{{ '}' }}
</{{ param.name }}>

{% endif %}{% endfor %}
{%- if with_schema %}
Return as JSON:
{{
  "result": "{{ result_field|default('Main result') }}",
  "details": "{{ details_field|default('Additional details') }}"
}}
{%- else %}
# TODO: Add specific prompt instructions
# Provide clear, structured guidance for the LLM
# Use JSON schema when structured output is needed
{%- endif %}"""
```

**Changes**:
- Use safer `param.get('optional', False)` check
- Cleaner JSON schema formatting
- Better TODO guidance

---

### Phase 3: Update Template Examples

**File**: `src/prompts/analysis.py` and `documentation.py`

#### 3.1 Update Existing Examples

Ensure all prompt examples in the template use the new patterns:

**Before**:
```python
from typing import Annotated

@mcp.prompt()
def summarize(
    document: Annotated[str, Field(description="...", min_length=1)],
) -> str:
```

**After**:
```python
@mcp.prompt
def summarize(
    document: str = Field(description="...", min_length=1),
) -> str:
```

**Key changes**:
- Remove `Annotated[]` wrapper
- Use simplified Field pattern
- Remove unnecessary `()` from decorator

#### 3.2 Add Dict Parameter Example

Add new example to `analysis.py`:

```python
@mcp.prompt
def analyze_data(
    data: dict[str, str] = Field(
        description=(
            "Data to analyze as a dictionary with string keys and values. "
            "Pass as JSON string."
        )
    ),
    analysis_type: str = Field(
        default="summary",
        description="Type of analysis: 'summary', 'detailed', or 'statistical'"
    ),
) -> str:
    """
    Analyze structured data and provide insights.

    This example demonstrates FastMCP 2.9.0+ dict parameter handling.
    Clients pass dict as JSON string, FastMCP converts automatically.

    Args:
        data: Dictionary of data to analyze
        analysis_type: Type of analysis to perform

    Returns:
        Formatted prompt for data analysis
    """
    return f"""Analyze the following data:

{data}

Perform a {analysis_type} analysis including:
1. Key patterns and trends
2. Notable outliers or anomalies
3. Statistical summaries (if applicable)
4. Actionable insights

Return results as structured JSON."""
```

---

### Phase 4: Update Documentation

#### 4.1 Update CLAUDE.md

**Add section** after the existing prompt documentation:

```markdown
## Prompt Parameter Types (FastMCP 2.9.0+)

### Supported Type Annotations

When defining prompt parameters, use these type patterns:

**Simple Types**:
- `str`, `int`, `float`, `bool`

**List Types** (must be parameterized):
- `list[str]`, `list[int]`, `list[float]`

**Dict Types** (must be parameterized):
- `dict[str, str]` - String keys and values
- `dict[str, Any]` - String keys, any JSON-serializable values
- `dict[str, int]`, `dict[str, float]`, etc.

**Optional Types** (use union syntax):
- `str | None`, `int | None`, `dict[str, str] | None`

⚠️ **Important**: Never use bare `dict` or `list` without type parameters.
FastMCP requires parameterized types to generate proper JSON schema hints for clients.

### Pattern: Field() with Defaults

```python
@mcp.prompt
def my_prompt(
    # Required parameter
    data: dict[str, str] = Field(
        description="Data dictionary (required)"
    ),

    # Optional parameter with default
    format: str = Field(
        default="json",
        description="Output format: 'json' or 'text'"
    ),

    # Optional parameter that can be None
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata dictionary"
    ),
) -> str:
    """Your prompt docstring."""
    return f"..."
```

### Why These Patterns Matter

1. **MCP Protocol Requirement**: MCP clients pass all arguments as strings
2. **FastMCP Conversion**: FastMCP auto-converts JSON strings to typed objects
3. **Schema Generation**: Parameterized types enable automatic schema hints
4. **Client Guidance**: Generated schemas tell clients the expected JSON format

### Example: MCP Client Usage

When you define:
```python
data: dict[str, str] = Field(description="User data")
```

FastMCP generates this for MCP clients:
```json
{
  "name": "data",
  "description": "User data\n\nProvide as JSON string matching: {\"additionalProperties\":{\"type\":\"string\"},\"type\":\"object\"}",
  "required": true
}
```

Clients then pass:
```json
{
  "data": "{\"name\": \"John\", \"email\": \"john@example.com\"}"
}
```

FastMCP automatically converts the JSON string to a Python dict.
```

#### 4.2 Update README.md

Add section under "Usage":

```markdown
### Generating Prompts with Parameters

Create prompts with properly typed parameters:

```bash
# Create a params.json file
cat > params.json << 'EOF'
[
  {
    "name": "data",
    "type": "dict[str, str]",
    "description": "Data to analyze as a dictionary",
    "required": true
  },
  {
    "name": "analysis_type",
    "type": "str",
    "description": "Type of analysis to perform",
    "default": "\"summary\"",
    "required": false
  }
]
EOF

# Generate the prompt
fips-agents generate prompt analyze_data \
  --description "Analyze structured data" \
  --params params.json \
  --with-schema
```

**Important Type Requirements**:
- Dict types must be parameterized: `dict[str, str]`, `dict[str, Any]`
- List types must be parameterized: `list[str]`, `list[int]`
- Use `| None` for optional types: `str | None`, `dict[str, str] | None`
- Defaults for strings must be quoted: `"\"default_value\""`
```

---

### Phase 5: Testing Strategy

#### 5.1 Add Unit Tests

**File**: `tests/test_generators.py`

Add tests for type validation:

```python
def test_validate_type_annotation_dict_requires_parameters():
    """Test that bare dict types are rejected."""
    is_valid, msg = validate_type_annotation("dict")
    assert not is_valid
    assert "type parameters" in msg.lower()

def test_validate_type_annotation_parameterized_dict_valid():
    """Test that parameterized dict types are accepted."""
    is_valid, msg = validate_type_annotation("dict[str, str]")
    assert is_valid
    assert msg == ""

def test_compute_type_hint_optional():
    """Test type hint computation for optional parameters."""
    param = {"type": "dict[str, str]", "optional": True}
    result = compute_type_hint(param)
    assert result == "dict[str, str] | None"

def test_compute_type_hint_required():
    """Test type hint computation for required parameters."""
    param = {"type": "str", "required": True}
    result = compute_type_hint(param)
    assert result == "str"
```

#### 5.2 Integration Tests

**File**: `tests/test_generate_prompts.py`

Add integration test:

```python
def test_generate_prompt_with_dict_params(tmp_path, mock_project):
    """Test generating a prompt with dict[str, str] parameters."""
    # Create params file with dict type
    params = [
        {
            "name": "data",
            "type": "dict[str, str]",
            "description": "Data dictionary",
            "required": True
        }
    ]
    params_file = tmp_path / "params.json"
    params_file.write_text(json.dumps(params))

    # Generate prompt
    result = CliRunner().invoke(
        cli,
        ["generate", "prompt", "test_prompt", "--params", str(params_file)],
        cwd=str(mock_project)
    )

    assert result.exit_code == 0

    # Verify generated code
    prompt_file = mock_project / "src/prompts/test_prompt.py"
    content = prompt_file.read_text()

    # Check for proper type annotation
    assert "dict[str, str]" in content
    assert "Field(" in content
    assert "description=" in content
```

#### 5.3 Manual Testing Checklist

- [ ] Generate prompt with `dict[str, str]` parameter
- [ ] Generate prompt with `dict[str, Any]` parameter
- [ ] Generate prompt with optional dict parameter
- [ ] Generate prompt with list and dict parameters together
- [ ] Verify generated code passes Python syntax validation
- [ ] Verify generated code works with FastMCP locally
- [ ] Deploy to OpenShift and verify arguments exposed via MCP
- [ ] Test with mcp-test-mcp tool to verify JSON string conversion

---

### Phase 6: Migration Guide

#### 6.1 For Existing Projects

**File**: Create `MIGRATION_GUIDE.md` in template root

```markdown
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
```

---

## Rollout Plan

### Phase 1: CLI Tool Updates (Week 1)
- [ ] Update `generators.py` with new type validation
- [ ] Add `validate_type_annotation()` function
- [ ] Add `compute_type_hint()` function
- [ ] Update `load_params_file()` validation
- [ ] Add unit tests for new functions
- [ ] Update CLI version to 0.2.0

### Phase 2: Template Updates (Week 1)
- [ ] Update `component.py.j2` with simplified pattern
- [ ] Update `test.py.j2` to match
- [ ] Remove helper variable generation
- [ ] Update example prompts in template
- [ ] Add new dict parameter example

### Phase 3: Documentation (Week 1)
- [ ] Update CLAUDE.md with new patterns
- [ ] Update README.md with examples
- [ ] Create MIGRATION_GUIDE.md
- [ ] Update ARCHITECTURE.md if needed
- [ ] Add inline template comments

### Phase 4: Testing (Week 2)
- [ ] Run unit tests on CLI changes
- [ ] Run integration tests on template
- [ ] Manual testing checklist
- [ ] Deploy test project to OpenShift
- [ ] Verify with mcp-test-mcp tool

### Phase 5: Release (Week 2)
- [ ] Tag CLI tool release v0.2.0
- [ ] Update template git tag
- [ ] Write release notes
- [ ] Update published docs
- [ ] Announce in team channels

---

## Risk Mitigation

### Breaking Changes

**Risk**: Existing projects with old params.json files will fail validation

**Mitigation**:
1. Make validation warnings initially, not errors
2. Provide clear error messages with fix instructions
3. Include migration guide in release notes
4. Version CLI tool so old template can use old CLI

### Type Complexity

**Risk**: Users confused by parameterized type requirements

**Mitigation**:
1. Provide clear examples in docs
2. Generate helpful error messages
3. Include type hints in JSON schema descriptions
4. Add FAQ section to docs

### Template Bugs

**Risk**: New template generates invalid Python syntax

**Mitigation**:
1. AST validation before writing files (already implemented)
2. Comprehensive test suite
3. Manual testing on real projects
4. Rollback plan (keep old template tagged)

---

## Success Criteria

- [ ] Generated prompts expose arguments via MCP protocol
- [ ] Dict parameters work with FastMCP auto-conversion
- [ ] All tests pass (unit + integration)
- [ ] Zero syntax errors in generated code
- [ ] Documentation complete and accurate
- [ ] Migration guide tested on real project
- [ ] No regressions in existing tool/resource/middleware generation

---

## Future Enhancements

### Phase 7 (Optional): Enhanced Type Support

Add support for more complex types:
- Nested dicts: `dict[str, dict[str, str]]` (may not work well per FastMCP docs)
- Custom Pydantic models (for advanced use cases)
- Discriminated unions
- Generic types

### Phase 8 (Optional): Interactive Type Builder

Add CLI interactive mode:
```bash
fips-agents generate prompt my_prompt --interactive
# Walks through parameter creation with type suggestions
```

### Phase 9 (Optional): Validation Linter

Create a linter for existing prompts:
```bash
fips-agents lint prompts
# Checks all prompts for FastMCP 2.9.0+ compliance
```

---

## Conclusion

This plan addresses all issues found during the weather-mcp debugging session:

1. ✅ Bare dict types → Parameterized dict types
2. ✅ Complex annotations → Simplified Field pattern
3. ✅ Unused imports → Clean imports
4. ✅ Auto-generated helpers → Natural conditional logic
5. ✅ Missing type validation → Comprehensive validation

Implementation follows the proven patterns from weather-mcp that successfully exposed prompt arguments via the MCP protocol with FastMCP 2.12.4.
