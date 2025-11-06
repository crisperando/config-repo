# generate_docs.py

A Python script that generates documentation for source code files, OpenAPI specs, and architecture by leveraging OpenAI's GPT models.

## Key points
- Uses environment variables to configure OpenAI API key, model names, and temperature.
- Scans source files in the base directory excluding common build and dependency folders.
- Generates DocUnit JSON documentation per source file by prompting OpenAI with code and path.
- Generates API documentation from OpenAPI YAML files if present.
- Generates an architecture markdown document from project context files.
- Writes generated documentation to a docs directory with structured markdown formatting.

## Public API
| Method | Purpose | Exceptions | Complexity |
|---|---|---|---|
| `def read(p: pathlib.Path) -> str` | Reads and returns the text content of a file at the given path with UTF-8 encoding. | FileNotFoundError, UnicodeDecodeError | O(n) where n is file size |
| `def write(p: pathlib.Path, text: str) -> None` | Writes the given text to a file at the specified path, creating parent directories if needed. | OSError | O(n) where n is length of text |
| `def render(tpl: str, **kwargs) -> str` | Replaces {{placeholders}} in the template string with corresponding keyword argument values. |  | O(m*k) where m is template length and k is number of placeholders |
| `def list_source_files() -> Iterator[pathlib.Path]` | Yields source code files with specific extensions in the base directory excluding ignored folders. |  | O(n) where n is number of files in base directory |
| `def ask_json(prompt: str) -> dict` | Sends a prompt to OpenAI chat completion API requesting JSON response; falls back to a secondary model on failure. | openai.error.OpenAIError, json.JSONDecodeError | Depends on network latency and model response time |
| `def ask_markdown(prompt: str) -> str` | Sends a prompt to OpenAI chat completion API requesting a markdown response. | openai.error.OpenAIError | Depends on network latency and model response time |
| `def write_docunit(md_path: pathlib.Path, unit: dict, src_path: str) -> None` | Writes a DocUnit dictionary as a formatted markdown file at the specified path. | OSError | O(n) where n is size of documentation content |
| `def gen_per_file() -> int` | Generates documentation markdown files for all source files found, returns count of files processed. | openai.error.OpenAIError, OSError | O(f) where f is number of source files |
| `def gen_api_from_openapi() -> bool` | Generates API documentation markdown files from OpenAPI YAML specs if any exist, returns success status. | openai.error.OpenAIError, OSError | O(s) where s is number of OpenAPI spec files |
| `def gen_arch() -> None` | Generates an architecture markdown document by reading project context files and prompting OpenAI. | openai.error.OpenAIError, OSError | O(c) where c is number of context files read |
| `def main() -> None` | Main CLI entry point that creates docs directory, generates documentation for source files, APIs, and architecture, then prints summary. | SystemExit | O(f + s + c) combined complexity of generation functions |

## Examples
```bash
export OPENAI_API_KEY="your_api_key"
python3 generate_docs.py
```

## Dependencies
- openai Python package
- Python 3 standard libraries: os, sys, json, re, pathlib

## Risks
- Requires valid OPENAI_API_KEY environment variable or exits.
- Relies on network connectivity and OpenAI API availability.
- Fallback model usage may produce different results.
- File system permissions may affect reading/writing files.
- Unknown behavior if source files contain unsupported encodings.

## Unknowns
- Exact format and structure of generated DocUnit JSON from OpenAI responses.
- Error handling details for OpenAI API failures beyond fallback usage.
- Performance characteristics on very large codebases.
- Specific environment variable descriptions beyond names and defaults.
- Whether the script supports incremental or partial documentation generation.
