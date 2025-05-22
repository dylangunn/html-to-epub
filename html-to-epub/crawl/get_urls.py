from bs4 import BeautifulSoup

def get_urls_from_index_file(index_html, paths):
    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    links = set()
    for a in soup.find_all("a", href=True):
        href = a['href']
        if 'chapter' in href: # TODO: Update logic
            links.add(href)
    print("found links")
    print(links)

    with open(paths.temp_urls, "w") as f:
        for link in sorted(links):
            f.write(link + "\n")
    
    return