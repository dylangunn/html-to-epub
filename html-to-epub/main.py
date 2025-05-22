import argparse
import os
from types import SimpleNamespace
from crawl.batch_download_webcontent import download_webcontent
from clean.clean_project_html import extract_chapters

def parse_args():
    parser = argparse.ArgumentParser(description="Robust wget downloader with retries and auto-resume support.")
    parser.add_argument("project_name", help="Name for output subfolder inside ./projects/")
    parser.add_argument("--retries", type=int, default=2, help="Number of retries for failed downloads (default: 2)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--index", help="URL of the index page containing a list of chapter links")
    group.add_argument("--index_file", help="Path to the file containing page content of the index page containing a list of chapter links")
    group.add_argument("--input_file", help="Path to the file containing list of URLs")

    return parser.parse_args()

def get_project_paths(project_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_output_dir = os.path.join(script_dir, "..", "projects", project_name)
    html_output_dir = os.path.join(base_output_dir, "html_output")
    temp_urls = os.path.join(base_output_dir, "temp_urls.txt")
    retry_urls = os.path.join(base_output_dir, "retry_urls.txt")
    final_failures_log = os.path.join(base_output_dir, "failed_final.txt")

    return SimpleNamespace(
        base_output_dir=base_output_dir,
        html_output_dir=html_output_dir,
        temp_urls=temp_urls,
        retry_urls=retry_urls,
        final_failures_log=final_failures_log
    )

def main():
    args = parse_args()
    paths = get_project_paths()

    download_webcontent(args, paths)
    extract_chapters(args, paths)