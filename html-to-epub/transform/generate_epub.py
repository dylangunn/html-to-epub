import argparse
import os
import subprocess
from natsort import natsorted
from types import SimpleNamespace

def parse_args():
    parser = argparse.ArgumentParser(description="Chapter extractor to clean and transform HTML chapter content to XHTML")
    parser.add_argument("project_name", help="Name for output subfolder inside ./projects/")
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", help="Overwrite existing EPUB")
    parser.set_defaults(overwrite=False)

    return parser.parse_args()

def get_project_paths(project_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_output_dir = os.path.join(script_dir, "..", "..", "projects", project_name)
    xhtml_dir = os.path.join(base_output_dir, "xhtml_output")
    output_epub = os.path.join(base_output_dir, project_name + ".epub")

    return SimpleNamespace(
        base_output_dir=base_output_dir,
        xhtml_dir=xhtml_dir,
        output_epub=output_epub
    )

def generate_epub(args, paths):
    if not args:
        args = parse_args()
    if not paths:
        paths = get_project_paths(args.project_name)

    if not os.path.exists(paths.xhtml_dir):
        print(f"\n❌ Failed to generate EPUB. XHTML directory does not exist: {paths.xhtml_dir}...")
        exit(1)
    elif os.path.exists(paths.output_epub) and not args.overwrite:
        print(f"\n⚠️ Skipping EPUB generation. EPUB already exists and --overwrite is set to False.")
        return

    xhtml_files = natsorted([
        os.path.join(paths.xhtml_dir, f) for f in os.listdir(paths.xhtml_dir)
        if f.endswith(".xhtml")
    ])

    if not xhtml_files:
        print("❌ No XHTML files found to convert.")
        return

    command = ["pandoc", *xhtml_files, "-o", paths.output_epub, "--toc", "--metadata", f"title={args.project_name}"]

    try:
        subprocess.run(command, check=True)
        print(f"📘 EPUB created: {paths.output_epub}")
    except subprocess.CalledProcessError as e:
        print(f"❌ EPUB generation failed: {e}")

if __name__ == "__main__":
    generate_epub(None, None)
