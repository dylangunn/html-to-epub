import argparse
import os
from types import SimpleNamespace
import trafilatura

def parse_args():
    parser = argparse.ArgumentParser(description="Chapter extractor to clean and transform HTML chapter content to XHTML")
    parser.add_argument("project_name", help="Name for output subfolder inside ./projects/")
    parser.add_argument("--no-overwrite", dest="overwrite", action="store_false", help="Do not overwrite existing XHTML files")
    parser.set_defaults(overwrite=True)

    return parser.parse_args()

def get_project_paths(project_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_output_dir = os.path.join(script_dir, "..", "..", "projects", project_name)
    html_output_dir = os.path.join(base_output_dir, "html_output")
    xhtml_output_dir = os.path.join(base_output_dir, "xhtml_output")

    os.makedirs(base_output_dir, exist_ok=True)
    os.makedirs(html_output_dir, exist_ok=True)
    os.makedirs(xhtml_output_dir, exist_ok=True)

    return SimpleNamespace(
        base_output_dir=base_output_dir,
        html_output_dir=html_output_dir,
        xhtml_output_dir=xhtml_output_dir
    )

def extract_chapters(args, paths):
    if not args:
        args = parse_args()
    if not paths:
        paths = get_project_paths(args.project_name)

    for filename in os.listdir(paths.html_output_dir):
        if not filename.endswith(".html"):
            continue

        html_path = os.path.join(paths.html_output_dir, filename)
        xhtml_path = os.path.join(paths.xhtml_output_dir, filename.replace(".html", ".xhtml"))

        if os.path.exists(xhtml_path) and not args.overwrite:
            print(f"⚠️ Skipping chapter cleaning (already exists): {filename}")
            continue

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        xhtml = trafilatura.extract(html, output_format='xml')

        if xhtml:
            with open(xhtml_path, "w", encoding="utf-8") as f:
                f.write(xhtml)
            print(f"✅ Extracted: {filename}")
        else:
            print(f"❌ Skipped (no extractable content): {filename}")
        
if __name__ == "__main__":
    extract_chapters(None, None)