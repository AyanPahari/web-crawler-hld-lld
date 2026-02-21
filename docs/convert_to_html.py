"""
Converts markdown docs to Google Docs-ready HTML files.

Usage:
  python3 docs/convert_to_html.py              # converts all docs
  python3 docs/convert_to_html.py part3        # converts only part3

Then open the generated HTML in Chrome:
  - Upload to Google Drive → right-click → Open with Google Docs
  - OR: Cmd+A, Cmd+C in browser → paste into new Google Doc
"""

import markdown
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FILES = [
    (
        "part2_scale_design.md",
        "part2_scale_design.html",
        "Scale Design: Operationalizing a Crawler for Billions of URLs",
    ),
    (
        "part3_poc_plan.md",
        "part3_poc_plan.html",
        "Engineering Plan: Proof of Concept to Production",
    ),
]

CSS = """
  body {
    font-family: 'Arial', sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #202124;
    max-width: 900px;
    margin: 40px auto;
    padding: 0 40px;
    background: #fff;
  }
  h1 {
    font-size: 22pt;
    font-weight: 700;
    color: #1a1a2e;
    border-bottom: 2px solid #4285f4;
    padding-bottom: 8px;
    margin-top: 32px;
  }
  h2 {
    font-size: 16pt;
    font-weight: 600;
    color: #1a1a2e;
    margin-top: 28px;
    border-left: 4px solid #4285f4;
    padding-left: 10px;
  }
  h3 {
    font-size: 13pt;
    font-weight: 600;
    color: #333;
    margin-top: 20px;
  }
  p { margin: 10px 0; }
  pre {
    background: #f8f9fa;
    border: 1px solid #dadce0;
    border-left: 4px solid #4285f4;
    border-radius: 4px;
    padding: 14px 16px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 9pt;
    line-height: 1.5;
    overflow-x: auto;
    white-space: pre;
  }
  code {
    background: #f1f3f4;
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 9.5pt;
  }
  pre code { background: none; padding: 0; font-size: 9pt; }
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 10.5pt;
  }
  th {
    background: #4285f4;
    color: #fff;
    font-weight: 600;
    padding: 9px 14px;
    text-align: left;
    border: 1px solid #3367d6;
  }
  td {
    padding: 8px 14px;
    border: 1px solid #dadce0;
    vertical-align: top;
  }
  tr:nth-child(even) td { background: #f8f9fa; }
  tr:hover td { background: #e8f0fe; }
  hr { border: none; border-top: 1px solid #dadce0; margin: 28px 0; }
  ul, ol { margin: 8px 0; padding-left: 24px; }
  li { margin: 4px 0; }
  blockquote {
    border-left: 4px solid #fbbc04;
    margin: 16px 0;
    padding: 8px 16px;
    background: #fefce8;
    color: #555;
  }
  @media print {
    body { margin: 20px; padding: 0; }
    pre { font-size: 8pt; }
  }
"""

filter_arg = sys.argv[1] if len(sys.argv) > 1 else None
targets = [f for f in FILES if filter_arg is None or filter_arg in f[0]]

for md_file, html_file, page_title in targets:
    input_path = os.path.join(SCRIPT_DIR, md_file)
    output_path = os.path.join(SCRIPT_DIR, html_file)

    with open(input_path, "r") as f:
        md_content = f.read()

    body_html = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc", "attr_list"],
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<style>{CSS}</style>
</head>
<body>
{body_html}
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    print(f"Generated: {output_path}")

print()
print("To import into Google Docs:")
print("  Option 1: Upload HTML to Google Drive → right-click → Open with Google Docs")
print("  Option 2: Open HTML in Chrome → Cmd+A → Cmd+C → paste into new Google Doc")
