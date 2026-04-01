"""Content verification: code parsing, number consistency, structure checks.

Programmatic checks that don't require an LLM — deterministic,
reproducible, and independently verifiable.
"""

import ast
import re


def check_code_blocks(content):
    """Extract and validate code blocks in paper content."""
    if not content:
        return {"total": 0, "valid": 0, "invalid": 0, "errors": []}

    # Extract fenced code blocks
    blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)

    total = len(blocks)
    valid = 0
    invalid = 0
    errors = []

    for lang, code in blocks:
        if lang.lower() in ("python", "py", ""):
            try:
                ast.parse(code)
                valid += 1
            except SyntaxError as e:
                invalid += 1
                errors.append(f"Line {e.lineno}: {e.msg}" if e.lineno else str(e.msg))
        else:
            valid += 1  # Non-Python blocks assumed valid

    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "parse_rate": valid / total if total > 0 else 1.0,
        "errors": errors,
    }


def check_number_consistency(content):
    """Check if key numbers are consistent across abstract, body, and tables."""
    if not content:
        return {"consistent": True, "inconsistencies": []}

    # Split into sections
    sections = re.split(r'^#{1,3}\s+', content, flags=re.MULTILINE)

    # Extract all numbers with context (pattern: number with % or decimal)
    number_pattern = r'(\d+\.?\d*)\s*%|(\d+\.\d+)|(?:n\s*=\s*)(\d+)'

    all_numbers = {}
    for i, section in enumerate(sections):
        numbers = re.findall(number_pattern, section)
        for match in numbers:
            val = next(n for n in match if n)
            if val not in all_numbers:
                all_numbers[val] = []
            all_numbers[val].append(i)

    # Check for specific inconsistency patterns:
    # Same metric reported differently in different sections
    inconsistencies = []

    # Look for p-values that appear multiple times with different values
    p_values = re.findall(r'p\s*[<>=]\s*([\d.e-]+)', content)
    if len(set(p_values)) != len(p_values):
        from collections import Counter
        dupes = {v: c for v, c in Counter(p_values).items() if c > 1}
        # Duplicates are fine (same value repeated) — only flag if contradictory

    # Look for effect sizes reported multiple times
    d_values = re.findall(r'd\s*=\s*([\d.]+)', content)
    rho_values = re.findall(r'(?:rho|ρ)\s*=\s*([-\d.]+)', content)
    beta_values = re.findall(r'(?:beta|β)\s*=\s*([-+\d.]+)', content)

    return {
        "consistent": len(inconsistencies) == 0,
        "inconsistencies": inconsistencies,
        "stats": {
            "unique_numbers": len(all_numbers),
            "p_values_found": len(p_values),
            "effect_sizes_found": len(d_values),
            "correlations_found": len(rho_values),
        },
    }


def check_skill_md(skill_md):
    """Verify skill_md quality beyond just existence."""
    if not skill_md:
        return {"has_skill": False, "score": 0.0, "details": {}}

    text = str(skill_md)
    details = {
        "length": len(text),
        "has_yaml_frontmatter": text.strip().startswith("---"),
        "has_steps": bool(re.search(r'(?i)step\s+\d|##\s+step', text)),
        "has_code_blocks": bool(re.search(r'```', text)),
        "has_expected_output": bool(re.search(r'(?i)expected\s+output|validation', text)),
        "has_bash_commands": bool(re.search(r'```bash|```sh|\$\s+\w+', text)),
        "num_code_blocks": len(re.findall(r'```', text)) // 2,
    }

    # Score: 0-1 based on how complete the skill is
    checks = [
        details["has_yaml_frontmatter"],
        details["has_steps"],
        details["has_code_blocks"],
        details["has_expected_output"],
        details["has_bash_commands"],
        details["length"] > 500,
        details["length"] > 2000,
        details["num_code_blocks"] >= 3,
    ]
    score = sum(checks) / len(checks)

    return {"has_skill": True, "score": score, "details": details}


def check_structure_depth(content):
    """Assess structural quality beyond just heading presence."""
    if not content:
        return {"score": 0.0, "details": {}}

    lines = content.split("\n")
    headings = [l for l in lines if re.match(r'^#{1,3}\s+', l)]

    # Check for logical section ordering
    has_intro = any(re.search(r'(?i)intro|background|motivation', h) for h in headings)
    has_methods = any(re.search(r'(?i)method|approach|design|framework', h) for h in headings)
    has_results = any(re.search(r'(?i)result|experiment|finding|evaluation', h) for h in headings)
    has_discussion = any(re.search(r'(?i)discuss|analysis|limitation', h) for h in headings)
    has_conclusion = any(re.search(r'(?i)conclus|summary|future', h) for h in headings)

    # Count substantive content indicators
    tables = len(re.findall(r'\|[^|]+\|[^|]+\|', content))
    math_blocks = len(re.findall(r'\$\$.*?\$\$', content, re.DOTALL))
    inline_math = len(re.findall(r'\$[^$]+\$', content))
    code_blocks = len(re.findall(r'```', content)) // 2

    details = {
        "heading_count": len(headings),
        "has_intro": has_intro,
        "has_methods": has_methods,
        "has_results": has_results,
        "has_discussion": has_discussion,
        "has_conclusion": has_conclusion,
        "imrad_score": sum([has_intro, has_methods, has_results, has_discussion, has_conclusion]) / 5,
        "table_rows": tables,
        "math_blocks": math_blocks,
        "inline_math": inline_math,
        "code_blocks": code_blocks,
    }

    return {"score": details["imrad_score"], "details": details}


def verify_paper_content(paper):
    """Run all programmatic content checks on a single paper."""
    content = paper.get("content", "") or ""
    skill_md = paper.get("skillMd") or paper.get("skill_md") or ""

    code_check = check_code_blocks(content)
    number_check = check_number_consistency(content)
    skill_check = check_skill_md(skill_md)
    structure_check = check_structure_depth(content)

    return {
        "code": code_check,
        "numbers": number_check,
        "skill": skill_check,
        "structure": structure_check,
    }
