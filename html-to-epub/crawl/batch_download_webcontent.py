import random
import subprocess
import time
import os
import argparse
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from types import SimpleNamespace
from get_urls import get_urls_from_index_file

# TODO: [Medium] Add a referer header to wget calls
# TODO: [Low] Add a prompt to inject cookies if required
# TODO: [Medium] Expand known error codes
# TODO: [Medium] Support error counting for generic "error" to be added to set later

known_errors = {
    "connection reset",
    "connection refused",
    "timed out",
    "error 403",
    "error 429"
}
error_counts = defaultdict(int)

FAIL_FAST_THRESHOLD = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

base_cmd = [
    "wget",
    "--limit-rate=100k",
    "--no-parent",
    "--no-directories",
    "--no-clobber",
    "--user-agent=" + USER_AGENT
]

def parse_args():
    parser = argparse.ArgumentParser(description="Robust wget downloader with retries and auto-resume support.")
    parser.add_argument("project_name", help="Name for output subfolder inside ./projects/")
    parser.add_argument("--retries", type=int, default=2, help="Number of retries for failed downloads (default: 2)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--index_file", help="Path to the file containing page content of the index page containing a list of chapter links")
    group.add_argument("--input_file", help="Path to the file containing list of URLs")

    return parser.parse_args()

def get_project_paths(project_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_output_dir = os.path.abspath(os.path.join(script_dir, "..", "..", "projects", project_name))
    html_output_dir = os.path.join(base_output_dir, "html_output")

    log_output_dir = os.path.join(base_output_dir, "logs")
    existing_logs = [f for f in os.listdir(log_output_dir) if f.startswith("log-attempt") and f.endswith(".txt")]
    attempt_nums = [int(f.split("log-attempt")[1].split(".txt")[0]) for f in existing_logs if f.split("log-attempt")[1].split(".txt")[0].isdigit()]
    next_log_num = max(attempt_nums) + 1 if attempt_nums else 1
    log_file = os.path.join(log_output_dir, f"log-attempt{next_log_num}.txt")

    temp_urls = os.path.join(base_output_dir, "temp_urls.txt")
    retry_urls = os.path.join(base_output_dir, "retry_urls.txt")
    final_failures_log = os.path.join(base_output_dir, "failed_final.txt")

    os.makedirs(base_output_dir, exist_ok=True)
    os.makedirs(html_output_dir, exist_ok=True)
    os.makedirs(log_output_dir, exist_ok=True)

    return SimpleNamespace(
        base_output_dir=base_output_dir,
        html_output_dir=html_output_dir,
        log_file=log_file,
        temp_urls=temp_urls,
        retry_urls=retry_urls,
        final_failures_log=final_failures_log
    )

def download_single_url(url, wait_time, html_output_dir, log_file):
    filename = url.rstrip("/").split("/")[-1] + ".html"
    output_path = os.path.join(html_output_dir, filename)

    if os.path.exists(output_path):
        print(f"⚠️ Skipping (already exists): {filename}")
        return ""
    
    cmd = base_cmd + [f"-O", output_path, url]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    jitter = random.uniform(0.5 * wait_time, 1.5 * wait_time)
    time.sleep(wait_time + jitter)
    
    output = []
    for line in process.stdout:
        print(line, end="")
        log_file.write(line)
        output.append(line)
    process.wait()
    log_file.flush()
    return "\n".join(output)

def run_fail_fast(urls, wait_time, log_file, html_output_dir):
    print("🧪 Running fail-fast")
    failed_urls = []
    consecutive_failures = 0
    for i, url in enumerate(urls):
        log_file.write(f"\n===== Attempt 0 - URL {i+1}: {url} =====\n")
        result_output = download_single_url(url, wait_time, html_output_dir, log_file)

        if any(err in result_output.lower() for err in known_errors):
            error_counts["fail-fast-triggered"] += 1
            failed_urls.append(url)
            consecutive_failures += 1
            if consecutive_failures >= FAIL_FAST_THRESHOLD:
                print(f"\n🚨 Fail-fast triggered: First {FAIL_FAST_THRESHOLD} consecutive URLs failed.")
                log_file.write(f"\n🚨 Fail-fast triggered after {FAIL_FAST_THRESHOLD} consecutive failures.\n")
                log_file.close()
                exit(1)
        else:
            consecutive_failures = 0  # reset on success

    return

def download_urls(wait_time, url_file, html_output_dir, log_file):
    with open(url_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    fail_fast_urls = urls[:5]
    urls = urls[5:]

    run_fail_fast(fail_fast_urls, wait_time, log_file, html_output_dir)
    
    output = []
    for i, url in enumerate(urls):
        output.extend(download_single_url(url, wait_time, html_output_dir, log_file))

    class Result:
        def __init__(self, text):
            self.stdout = text
            self.stderr = ""

    return Result("\n".join(output))

def extract_failed_urls(log_text):
    failed_urls = []
    for line in log_text.splitlines():
        lower_line = line.lower()
        if "url:" in lower_line:
            for err in known_errors:
                if err in lower_line:
                    error_counts[err] += 1
                    parts = line.split("URL:")
                    if len(parts) > 1:
                        failed_url = parts[1].strip()
                        failed_urls.append(failed_url)
                    break  # avoid double-counting
    return list(set(failed_urls))

def download_webcontent(args, paths):
    if not args:
        args = parse_args()
    if not paths:
        paths = get_project_paths(args.project_name)
    wait_time = 3

    log_file = open(paths.log_file, "w", encoding="utf-8")
    print(f"📄 Logging to {paths.log_file}")

    if args.index_file:
        print("Reading from index file")
        get_urls_from_index_file(args.index_file, paths)
        url_file = paths.temp_urls
    else: 
        print("Reading from pre-created url file or previous url failures file")
        url_file = paths.final_failures_log if os.path.exists(paths.final_failures_log) else args.input_file
    print(f"📁 Starting URL file: {url_file}")

    final_failures = []
    for attempt in range(1, 2 + args.retries):
        log_file.write(f"\n===== Attempt {attempt} (wait={wait_time}s) =====\n")
        result = download_urls(wait_time, url_file, paths.html_output_dir, log_file)
        log_file.write("STDOUT:\n" + result.stdout + "\n")
        log_file.flush()

        failed_urls = extract_failed_urls(result.stdout)

        if not failed_urls:
            print("✅ All downloads completed successfully.")
            if os.path.exists(paths.final_failures_log):
                os.remove(paths.final_failures_log)
            break

        print(f"⚠️ Attempt {attempt}: {len(failed_urls)} URLs failed. Retrying with wait={wait_time + 2}s...")

        with open(paths.retry_urls, "w") as f:
            for url in failed_urls:
                f.write(url + "\n")

        final_failures = failed_urls
        url_file = paths.retry_urls
        wait_time += 2
        time.sleep(wait_time)

    else:
        print(f"\n❌ Some downloads failed after all retries. Logging to {paths.final_failures_log}...")
        with open(paths.final_failures_log, "w") as f:
            for url in final_failures:
                f.write(url + "\n")
        print(f"📝 {len(final_failures)} URLs logged in {paths.final_failures_log} for later resumption.")

    if error_counts:
        print("\n📊 Error summary:")
        log_file.write("\n📊 Error summary:\n")
        for err, count in error_counts.items():
            print(f"  {err}: {count}")
            log_file.write(f"  {err}: {count}\n")

    if os.path.exists(paths.retry_urls):
        os.remove(paths.retry_urls)

    log_file.close()

if __name__ == "__main__":
    download_webcontent(None, None)