#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json, re, pathlib
from openai import OpenAI

MODEL_PRIMARY  = os.getenv("OPENAI_MODEL_PRIMARY",  "gpt-4.1-mini")
MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4.1")
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

SYSTEM_DOC = (
    "You are an expert software documentation generator. "
    "Read only the provided inputs. Be concise and factual. "
    "If unsure, write 'unknown' in the 'unknowns' array. "
    "Never invent APIs not present in the code."
)

# ---------- PROMPTS (now using {{placeholders}}) ----------
PROMPT_SUMMARIZE_CODE = """You are documenting production code for other engineers.
STRICT RULES:
- Use only the provided code + file path to infer behavior.
- If a detail isn't in the text, respond "unknown" (add it in "unknowns").
- Output VALID JSON that matches the DocUnit schema exactly.
- Be concise and specific; no marketing language.

DocUnit JSON schema (shape only):
{
  "title": "string",
  "summary": "string",
  "key_points": ["string"],
  "public_api": [
    {"name":"string","signature":"string","purpose":"string","exceptions":["string"],"complexity":"string"}
  ],
  "usage_examples": [{"language":"string","code":"string"}],
  "dependencies": ["string"],
  "risks": ["string"],
  "unknowns": ["string"]
}

Inputs:
- Path: {{path}}
- Language: {{language}}
- Code:
---
{{code}}
---
Now produce ONLY the DocUnit JSON.
"""

PROMPT_API_PAGE = """You are a technical writer. Convert this OpenAPI YAML to clean Markdown.
Include:
- Endpoint table (Method, Path, Summary, Auth).
- Request/response examples (curl + Java + C#).
- Error catalogue with HTTP codes + example JSON.
- Authentication section if securitySchemes exist.

OpenAPI YAML:
---
{{openapi}}
---
Return ONLY Markdown.
"""

PROMPT_ARCH = """Create a single Markdown 'Architecture' page with:
- Mermaid component diagram of services & data stores.
- Mermaid sequence diagram for a happy-path call.
- Service matrix (service, port, depends-on, environment).
- Environment variables table (name, description, default).
- Operational runbook: start, health, logs, stop (commands).

Context:
---
{{context}}
---
Return ONLY Markdown.
"""

# ---------- PATHS ----------
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
BASE_DIR   = SCRIPT_DIR
DOCS_DIR   = BASE_DIR / "docs"

# ---------- OPENAI ----------
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Set OPENAI_API_KEY.", file=sys.stderr); sys.exit(1)
client = OpenAI(api_key=api_key)

# ---------- HELPERS ----------
def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")

def write(p: pathlib.Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def render(tpl: str, **kwargs) -> str:
    # Only replace our {{name}} tokens; leave normal JSON {} alone
    for k, v in kwargs.items():
        tpl = tpl.replace(f"{{{{{k}}}}}", v)
    return tpl

def list_source_files():
    exts = (".java",".kt",".cs",".js",".ts",".py",".go")
    ignore = re.compile(r"(?:^|/)(target|bin|node_modules|\.git|build|dist|out|docs|.venv)(?:/|$)")
    for p in BASE_DIR.rglob("*"):
        if p.is_file() and p.suffix in exts:
            rel = p.relative_to(BASE_DIR).as_posix()
            if not ignore.search(rel):
                yield p

def ask_json(prompt: str) -> dict:
    try:
        r = client.chat.completions.create(
            model=MODEL_PRIMARY, temperature=TEMP,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_DOC},
                {"role": "user",   "content": prompt}
            ],
        )
        return json.loads(r.choices[0].message.content)
    except Exception:
        r = client.chat.completions.create(
            model=MODEL_FALLBACK, temperature=TEMP,
            messages=[
                {"role": "system", "content": SYSTEM_DOC},
                {"role": "user",   "content": prompt + "\n\nReturn ONLY valid JSON."}
            ],
        )
        return json.loads(r.choices[0].message.content)

def ask_markdown(prompt: str) -> str:
    r = client.chat.completions.create(
        model=MODEL_PRIMARY, temperature=TEMP,
        messages=[
            {"role": "system", "content": SYSTEM_DOC},
            {"role": "user",   "content": prompt}
        ],
    )
    return r.choices[0].message.content

# ---------- GENERATORS ----------
def write_docunit(md_path: pathlib.Path, unit: dict, src_path: str) -> None:
    md = []
    md += [f"# {unit.get('title', pathlib.Path(src_path).name)}", ""]
    md += [unit.get("summary",""), ""]

    if unit.get("key_points"):
        md += ["## Key points"] + [f"- {x}" for x in unit["key_points"]] + [""]

    if unit.get("public_api"):
        md += ["## Public API",
               "| Method | Purpose | Exceptions | Complexity |",
               "|---|---|---|---|"]
        for m in unit["public_api"]:
            md.append(f"| `{m.get('signature','')}` | {m.get('purpose','')} | "
                      f"{', '.join(m.get('exceptions',[]))} | {m.get('complexity','')} |")
        md.append("")

    if unit.get("usage_examples"):
        md += ["## Examples"]
        for ex in unit["usage_examples"]:
            md += [f"```{ex.get('language','')}\n{ex.get('code','')}\n```"]
        md.append("")

    if unit.get("dependencies"):
        md += ["## Dependencies"] + [f"- {d}" for d in unit["dependencies"]] + [""]

    if unit.get("risks"):
        md += ["## Risks"] + [f"- {r}" for r in unit["risks"]] + [""]

    if unit.get("unknowns"):
        md += ["## Unknowns"] + [f"- {u}" for u in unit["unknowns"]] + [""]

    write(md_path, "\n".join(md))

def gen_per_file() -> int:
    out_root = DOCS_DIR / "code"
    count = 0
    for p in list_source_files():
        prompt = render(
            PROMPT_SUMMARIZE_CODE,
            path=str(p.relative_to(BASE_DIR)).replace("\\","/"),
            language=p.suffix.lstrip("."),
            code=read(p),
        )
        unit = ask_json(prompt)
        out = out_root / (str(p.relative_to(BASE_DIR)).replace(os.sep,"/") + ".md")
        write_docunit(out, unit, str(p))
        count += 1
    return count

def gen_api_from_openapi() -> bool:
    specs = list(BASE_DIR.rglob("openapi*.y*ml"))
    if not specs:
        return False
    for spec in specs:
        md = ask_markdown(render(PROMPT_API_PAGE, openapi=read(spec)))
        write(DOCS_DIR / f"api/{spec.stem}.md", md)
    return True

def gen_arch() -> None:
    bits = []
    for name in ["README.md","docker-compose.yml","pom.xml","build.gradle","settings.gradle","package.json"]:
        p = BASE_DIR / name
        if p.exists():
            bits.append(f"\n## {name}\n```text\n{read(p)}\n```")
    md = ask_markdown(render(PROMPT_ARCH, context="\n".join(bits) or "No context."))
    write(DOCS_DIR / "architecture.md", md)

# ---------- CLI ----------
def main():
    DOCS_DIR.mkdir(exist_ok=True)
    n = gen_per_file()
    gen_api_from_openapi()
    gen_arch()
    print(f"Generated/updated docs for {n} source files.")

if __name__ == "__main__":
    main()
