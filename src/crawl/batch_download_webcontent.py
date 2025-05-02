import random
import subprocess
import time
import os
import argparse
from collections import defaultdict
from types import SimpleNamespace

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

wait_time = 3   # 3s is ~20 req/min
fail_fast_threshold = 3

base_cmd = [
    "wget",
    "--random-wait",
    "--limit-rate=100k",
    "--no-clobber",
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
]

def parse_arguments():
    parser = argparse.ArgumentParser(description="Robust wget downloader with retries and auto-resume support.")
    parser.add_argument("input_file", help="Path to the file containing list of URLs")
    parser.add_argument("project_name", help="Name for output subfolder inside ./projects/")
    parser.add_argument("--retries", type=int, default=2, help="Number of retries for failed downloads (default: 2)")
    return parser.parse_args()

def get_project_paths(project_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_output_dir = os.path.join(script_dir, "..", "..", "projects", project_name)
    html_output_dir = os.path.join(base_output_dir, "html_output")
    temp_urls = os.path.join(base_output_dir, "retry_urls.txt")
    final_failures_log = os.path.join(base_output_dir, "failed_final.txt")

    return SimpleNamespace(
        base_output_dir=base_output_dir,
        html_output_dir=html_output_dir,
        temp_urls=temp_urls,
        final_failures_log=final_failures_log
    )

def download_single_url(url, wait_time):
    cmd = base_cmd + [f"--wait={wait_time}", "-P", html_output_dir, url]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = []
    for line in process.stdout:
        print(line, end="")
        log_file.write(line)
        output.append(line)
    process.wait()
    log_file.flush()
    return "\n".join(output)

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
            self.stderr = ""  # Merged stderr into stdout

    return Result("".join(output_lines))

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

def run_fail_fast_first_attempt(urls, wait_time, attempt):
    print("🧪 Running fail-fast first attempt (one-by-one)")
    failed_urls = []
    consecutive_failures = 0
    for i, url in enumerate(urls):
        log_file.write(f"\n===== Attempt {attempt} - URL {i+1}: {url} =====\n")
        result_output = download_single_url(url, wait_time)

        if any(err in result_output.lower() for err in known_errors):
            error_counts["fail-fast-triggered"] += 1
            failed_urls.append(url)
            consecutive_failures += 1
            if consecutive_failures >= fail_fast_threshold:
                print(f"\n🚨 Fail-fast triggered: First {fail_fast_threshold} consecutive URLs failed.")
                log_file.write(f"\n🚨 Fail-fast triggered after {fail_fast_threshold} consecutive failures.\n")
                log_file.close()
                exit(1)
        else:
            consecutive_failures = 0  # reset on success

        jitter = random.uniform(0.5 * wait_time, 1.5 * wait_time)
        time.sleep(wait_time + jitter)  # Wait between individual wget calls

    return failed_urls


def download_webcontent():
    args = parse_arguments()
    paths = get_project_paths(args.project_name)

    # === Determine next available log file ===
    os.makedirs(paths.base_output_dir, exist_ok=True)
    os.makedirs(paths.html_output_dir, exist_ok=True)
    existing_logs = [f for f in os.listdir(paths.base_output_dir) if f.startswith("log-attempt") and f.endswith(".txt")]
    attempt_nums = [int(f.split("log-attempt")[1].split(".txt")[0]) for f in existing_logs if f.split("log-attempt")[1].split(".txt")[0].isdigit()]
    next_log_num = max(attempt_nums) + 1 if attempt_nums else 1
    log_file_path = os.path.join(paths.base_output_dir, f"log-attempt{next_log_num}.txt")
    log_file = open(log_file_path, "w", encoding="utf-8")
    print(f"📄 Logging to {log_file_path}")

    # Determine starting URL file (fresh or resume)
    url_file = paths.final_failures_log if os.path.exists(paths.final_failures_log) else args.input_file
    print(f"📁 Starting URL file: {url_file}")
    final_failures = []

    # Run fail-fast pre-check
    with open(url_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    fail_fast_urls = urls[:fail_fast_threshold]
    _ = run_fail_fast_first_attempt(fail_fast_urls, wait_time, attempt=0)  # 0 = preflight

    for attempt in range(1, 2 + args.retries):
        result = download_urls(wait_time, url_file)
        log_file.write(f"\n===== Attempt {attempt} (wait={wait_time}s) =====\n")
        log_file.write("STDOUT:\n" + result.stdout + "\n")
        log_file.write("STDERR:\n" + result.stderr + "\n")
        log_file.flush()

        failed_urls = extract_failed_urls(result.stdout)

        if not failed_urls:
            print("✅ All downloads completed successfully.")
            if os.path.exists(paths.final_failures_log):
                os.remove(paths.final_failures_log)
            break

        print(f"⚠️ Attempt {attempt}: {len(failed_urls)} URLs failed. Retrying with wait={wait_time + 2}s...")

        with open(paths.temp_urls, "w") as f:
            for url in failed_urls:
                f.write(url + "\n")

        final_failures = failed_urls
        url_file = paths.temp_urls
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

    if os.path.exists(paths.temp_urls):
        os.remove(paths.temp_urls)

    log_file.close()

if __name__ == "__main__":
    download_webcontent()