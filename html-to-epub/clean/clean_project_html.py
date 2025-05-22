import argparse
import os
import re
from types import SimpleNamespace
import trafilatura
from bs4 import BeautifulSoup

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
    skipped_chapters = 0
    for filename in os.listdir(paths.html_output_dir):
        if not filename.endswith(".html"):
            continue

        html_path = os.path.join(paths.html_output_dir, filename)
        xhtml_path = os.path.join(paths.xhtml_output_dir, filename.replace(".html", ".xhtml"))

        if os.path.exists(xhtml_path) and not args.overwrite:
            skipped_chapters += 1
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

    print(f"⚠️ Skipped cleaning {skipped_chapters} chapter(s) (already exist)")

def title_case(text):
    """
    Convert text to title case while keeping certain words lowercase.
    """
    # Words that should not be capitalized in titles
    lowercase_words = {'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 
                      'in', 'to', 'at', 'by', 'of'}
    
    # Special words that should always be capitalized a certain way
    special_cases = {
        'part': 'Part',
        'i': 'I',
        'ii': 'II',
        'iii': 'III',
        'iv': 'IV',
        'v': 'V'
    }

    words = text.split()
    
    # Always capitalize the first word
    if words:
        words[0] = words[0].capitalize()
    
    # Process remaining words
    for i in range(1, len(words)):
        word = words[i].lower()
        
        # Check for special cases first
        if word in special_cases:
            words[i] = special_cases[word]
        # Check if it's a word that should remain lowercase
        elif word not in lowercase_words:
            words[i] = word.capitalize()
        else:
            words[i] = word
            
    return ' '.join(words)

def clean_chapter_title(filename):
    """
    Clean chapter titles to a consistent format with proper capitalization.
    """
    # Remove file extension and replace hyphens with spaces
    base_name = os.path.splitext(filename)[0].replace('-', ' ')
    
    # Try to find chapter number and subtitle
    chapter_pattern = re.compile(r'.*?chapter\s*(\d+)[:\s]*(.+)?', re.IGNORECASE)
    match = chapter_pattern.search(base_name)
    
    if match:
        chapter_num = match.group(1)
        subtitle = match.group(2)
        if subtitle:
            # Clean up and properly capitalize the subtitle
            subtitle = subtitle.strip()
            subtitle = title_case(subtitle)
            return f"Chapter {chapter_num}: {subtitle}"
        else:
            return f"Chapter {chapter_num}"
    
    # Fallback: try to just find a number if no "Chapter" pattern exists
    number_match = re.search(r'\d+', base_name)
    if number_match:
        return f"Chapter {number_match.group()}"
    
    # Last resort: title case the whole thing
    return title_case(base_name)

def fix_format(xhtml_dir):
    patched = 0
    for filename in os.listdir(xhtml_dir):
        if not filename.endswith(".xhtml"):
            continue

        file_path = os.path.join(xhtml_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "lxml-xml")

        print(f"Attempting to fix XHTML format of {filename}...")

        # Convert <main> to <body>
        main_tag = soup.find("main")
        if main_tag:
            body_tag = soup.new_tag("body")
            for child in list(main_tag.contents):
                body_tag.append(child.extract())
            main_tag.replace_with(body_tag)

        # Get cleaned chapter title
        clean_title = clean_chapter_title(filename)

        # Create or update h1 tag with cleaned title
        existing_h1 = body_tag.find("h1")
        if existing_h1:
            existing_h1.string = clean_title
        else:
            new_h1 = soup.new_tag("h1")
            new_h1.string = clean_title
            body_tag.insert(0, new_h1)

        # Remove any remaining fake h1 (head with rend="h1")
        fake_h1 = body_tag.find("head", {"rend": "h1"})
        if fake_h1:
            fake_h1.decompose()

        # Ensure <html><head> structure exists
        if not soup.find("html"):
            html_tag = soup.new_tag("html", xmlns="http://www.w3.org/1999/xhtml")
            head_tag = soup.new_tag("head")
            meta_tag = soup.new_tag("meta", charset="utf-8")
            head_tag.append(meta_tag)
            html_tag.append(head_tag)
            html_tag.append(body_tag)
            soup = BeautifulSoup(str(html_tag), "lxml-xml")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        patched += 1

    print(f"✅ Patched {patched} files with cleaned chapter titles.")

def clean_project(args, paths):
    if not args:
        args = parse_args()
    if not paths:
        paths = get_project_paths(args.project_name)

    extract_chapters(args, paths)
    fix_format(paths.xhtml_output_dir)
        
if __name__ == "__main__":
    clean_project(None, None)