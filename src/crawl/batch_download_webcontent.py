import subprocess
import time
import os
import argparse

# Default wait time of 4s corresponds to ~15 req/min
# Starts conservative to prevent detection by site
wait_time = 4

# CLI argument setup
parser = argparse.ArgumentParser(description="Robust wget downloader with retries and auto-resume support.")
parser.add_argument("input_file", help="Path to the file containing list of URLs")
parser.add_argument("project_name", help="Name for output subfolder inside ./projects/")
parser.add_argument("--retries", type=int, default=2, help="Number of retries for failed downloads (default: 2)")
args = parser.parse_args()

# === Derived paths ===
script_dir = os.path.dirname(os.path.abspath(__file__))
base_output_dir = os.path.join(script_dir, "..", "..", "projects", args.project_name)
html_output_dir = os.path.join(base_output_dir, "html_output")
temp_urls = os.path.join(base_output_dir, "retry_urls.txt")
final_failures_log = os.path.join(base_output_dir, "failed_final.txt")

# === Determine next available log file ===
existing_logs = [f for f in os.listdir(base_output_dir) if f.startswith("log-attempt") and f.endswith(".txt")]
attempt_nums = [int(f.split("log-attempt")[1].split(".txt")[0]) for f in existing_logs if f.split("log-attempt")[1].split(".txt")[0].isdigit()]
next_log_num = max(attempt_nums) + 1 if attempt_nums else 1
log_file_path = os.path.join(base_output_dir, f"log-attempt{next_log_num}.txt")
log_file = open(log_file_path, "w", encoding="utf-8")
print(f"📄 Logging to {log_file_path}")

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

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    output_lines = []
    for line in process.stdout:
        print(line, end="")        # Live terminal output
        log_file.write(line)       # Write to log
        output_lines.append(line)  # Store for error parsing
    process.wait()
    log_file.flush()

    # Return collected output as a mock `CompletedProcess`-like object
    class Result:
        def __init__(self, text):
            self.stdout = text
            self.stderr = ""  # We merged stderr into stdout

    return Result("".join(output_lines))

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

for attempt in range(1, 2 + args.retries):
    result = download_urls(wait_time, url_file)
    log_file.write(f"\n===== Attempt {attempt} (wait={wait_time}s) =====\n")
    log_file.write("STDOUT:\n" + result.stdout + "\n")
    log_file.write("STDERR:\n" + result.stderr + "\n")
    log_file.flush()  # Optional: write to disk immediately

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
    wait_time += 3
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

log_file.close()
