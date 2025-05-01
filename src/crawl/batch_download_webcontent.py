import subprocess
import time
import os
import argparse

# Base arguments
wait_time = 2

# CLI argument setup
parser = argparse.ArgumentParser(description="Robust wget downloader with retries and auto-resume support.")
parser.add_argument("input_file", help="Path to the file containing list of URLs")
parser.add_argument("project_name", help="Name for output subfolder inside ./projects/")
parser.add_argument("--retries", type=int, default=3, help="Number of retries for failed downloads (default: 3)")
args = parser.parse_args()

# === Derived paths ===
script_dir = os.path.dirname(os.path.abspath(__file__))
base_output_dir = os.path.join(script_dir, "..", "..", "projects", args.project_name)
html_output_dir = os.path.join(base_output_dir, "html_output")
temp_urls = os.path.join(base_output_dir, "retry_urls.txt")
final_failures_log = os.path.join(base_output_dir, "failed_final.txt")

# Wget base command
base_cmd = [
    "wget",
    "--random-wait",
    "--limit-rate=100k",
    "--no-clobber",
]

def download_urls(wait_time, url_file):
    cmd = base_cmd + [f"--wait={wait_time}", "-i", url_file, "-P", html_output_dir]
    print(f"\n⏳ Running wget with wait={wait_time}s ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def extract_failed_urls(log_text):
    failed_urls = []
    for line in log_text.splitlines():
        if ("error 429" in line.lower() or "timed out" in line.lower()) and "url:" in line.lower():
            parts = line.split("URL:")
            if len(parts) > 1:
                failed_url = parts[1].strip()
                failed_urls.append(failed_url)
    return list(set(failed_urls))

# === Setup output structure ===
os.makedirs(html_output_dir, exist_ok=True)

# Determine starting URL file (fresh or resume)
url_file = final_failures_log if os.path.exists(final_failures_log) else args.input_file
print(f"📁 Starting URL file: {url_file}")
final_failures = []

for attempt in range(1, args.retries + 1):
    result = download_urls(wait_time, url_file)

    failed = extract_failed_urls(result.stderr + result.stdout)

    if not failed:
        print("✅ All downloads completed successfully.")
        if os.path.exists(final_failures_log):
            os.remove(final_failures_log)
        break

    print(f"⚠️ Attempt {attempt}: {len(failed)} URLs failed. Retrying with wait={wait_time + 2}s...")

    with open(temp_urls, "w") as f:
        for url in failed:
            f.write(url + "\n")

    final_failures = failed
    url_file = temp_urls
    wait_time += 2
    time.sleep(wait_time)

else:
    print(f"\n❌ Some downloads failed after all retries. Logging to {final_failures_log}...")
    with open(final_failures_log, "w") as f:
        for url in final_failures:
            f.write(url + "\n")
    print(f"📝 {len(final_failures)} URLs logged in {final_failures_log} for later resumption.")

# Cleanup
if os.path.exists(temp_urls):
    os.remove(temp_urls)
