"""
Converts part2_scale_design.md to a Google Docs-ready HTML file.
Run: python3 docs/convert_to_html.py
Then open the generated HTML in Chrome, Cmd+A, Cmd+C, paste into Google Docs.
"""

import markdown
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(SCRIPT_DIR, "part2_scale_design.md")
OUTPUT = os.path.join(SCRIPT_DIR, "part2_scale_design.html")

with open(INPUT, "r") as f:
    md_content = f.read()

# extensions: tables, fenced code blocks, attribute lists
body_html = markdown.markdown(
    md_content,
    extensions=["tables", "fenced_code", "toc", "attr_list"],
)

# inline CSS styled for Google Docs import — clean, professional
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scale Design: Operationalizing a Crawler for Billions of URLs</title>
<style>
  body {{
    font-family: 'Arial', sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #202124;
    max-width: 900px;
    margin: 40px auto;
    padding: 0 40px;
    background: #fff;
  }}

  h1 {{
    font-size: 22pt;
    font-weight: 700;
    color: #1a1a2e;
    border-bottom: 2px solid #4285f4;
    padding-bottom: 8px;
    margin-top: 32px;
  }}

  h2 {{
    font-size: 16pt;
    font-weight: 600;
    color: #1a1a2e;
    margin-top: 28px;
    border-left: 4px solid #4285f4;
    padding-left: 10px;
  }}

  h3 {{
    font-size: 13pt;
    font-weight: 600;
    color: #333;
    margin-top: 20px;
  }}

  p {{
    margin: 10px 0;
  }}

  /* Code blocks — architecture diagrams */
  pre {{
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
  }}

  code {{
    background: #f1f3f4;
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 9.5pt;
  }}

  pre code {{
    background: none;
    padding: 0;
    font-size: 9pt;
  }}

  /* Tables */
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 10.5pt;
  }}

  th {{
    background: #4285f4;
    color: #fff;
    font-weight: 600;
    padding: 9px 14px;
    text-align: left;
    border: 1px solid #3367d6;
  }}

  td {{
    padding: 8px 14px;
    border: 1px solid #dadce0;
    vertical-align: top;
  }}

  tr:nth-child(even) td {{
    background: #f8f9fa;
  }}

  tr:hover td {{
    background: #e8f0fe;
  }}

  /* Horizontal rules as section breaks */
  hr {{
    border: none;
    border-top: 1px solid #dadce0;
    margin: 28px 0;
  }}

  ul, ol {{
    margin: 8px 0;
    padding-left: 24px;
  }}

  li {{
    margin: 4px 0;
  }}

  blockquote {{
    border-left: 4px solid #fbbc04;
    margin: 16px 0;
    padding: 8px 16px;
    background: #fefce8;
    color: #555;
  }}

  /* Page break hint for printing */
  h2 {{
    page-break-before: auto;
  }}

  @media print {{
    body {{ margin: 20px; padding: 0; }}
    pre {{ font-size: 8pt; }}
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

with open(OUTPUT, "w") as f:
    f.write(html)

print(f"Generated: {OUTPUT}")
print()
print("To import into Google Docs:")
print("  1. Open the HTML file in Chrome")
print("  2. Cmd+A (select all), then Cmd+C (copy)")
print("  3. Open a new Google Doc and Cmd+V (paste)")
print("  OR")
print("  1. Upload the HTML file to Google Drive")
print("  2. Right-click > Open with > Google Docs")
