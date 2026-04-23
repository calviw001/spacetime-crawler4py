import re
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
import lxml
from hashlib import sha256

# Add global variables here:
unique_urls = set()
num_words_per_url = {}
common_word_frequencies = {}
subdomains = {}

hashes = set()

stopwords = set([
    "a",          "about",      "above",      "after",
    "again",      "against",    "all",        "am",
    "an",         "and",        "any",        "are",
    "aren't",     "as",         "at",         "be",
    "because",    "been",       "before",     "being",
    "below",      "between",    "both",       "but",
    "by",         "can't",      "cannot",     "could",
    "couldn't",   "did",        "didn't",     "do",
    "does",       "doesn't",    "doing",      "don't",
    "down",       "during",     "each",       "few",
    "for",        "from",       "further",    "had",
    "hadn't",     "has",        "hasn't",     "have",
    "haven't",    "having",     "he",         "he'd",
    "he'll",      "he's",       "her",        "here",
    "here's",     "hers",       "herself",    "him",
    "himself",    "his",        "how",        "how's",
    "i",          "i'd",        "i'll",       "i'm",
    "i've",       "if",         "in",         "into",
    "is",         "isn't",      "it",         "it's",
    "its",        "itself",     "let's",      "me",
    "more",       "most",       "mustn't",    "my",
    "myself",     "no",         "nor",        "not",
    "of",         "off",        "on",         "once",
    "only",       "or",         "other",      "ought",
    "our",        "ours"
])

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def has_informative_content():
    # Return true if the page has high textual information content, and return false otherwise
    pass

def is_a_trap():
    # Return true is the site is a crawler trap, and return false otherwise
    pass

def is_page_similar(page_text):
    # Return true if the page is too similar to a previously crawled page, and return false otherwise

    # Compute the hash of the provided webpage text
    text_to_hash = page_text[:10000] if len(page_text) > 10000 else page_text
    page_hash = sha256(text_to_hash.encode('utf-8')).hexdigest()
    
    # Check if the hash was already seen
    if page_hash in hashes:
        return True
    else:
        hashes.add(page_hash)
        return False

def is_too_large():
    # Return true if the file is too large, and return false otherwise
    pass

def word_has_no_digits(word):
    # Return true if the given word has no digits 0-9, and return false otherwise
    if any(char.isdigit() for char in word):
        return False
    return True

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    # Create a list that will hold all links extracted from the page
    links = list()

    # Return an empty list if the status code is not 200
    if resp.status != 200:
        return links

    # Get the page content
    page_content = resp.raw_response.content

    # Return an empty list if there is no page content
    if not resp.raw_response or not page_content:
        return links

    try:
        soup = BeautifulSoup(page_content, 'lxml')
        
        # Remove script and style tags...
        for script_or_style in soup(["script", "style"]):
            script_or_style.extract()

        # ...and then get the webpage text
        webpage_text = " ".join(soup.get_text().replace("\n", " ").split())

        # If the webpage text is too similar/is identical to some previous webpage text that was already scraped, then return an empty list
        if is_page_similar(webpage_text):
            return links  

        # Collect all the words from the webpage INCLUDING stopwords for right now
        pattern = r"\b\S+\b"
        all_words = re.findall(pattern, webpage_text)
        all_words = list((word for word in all_words if word_has_no_digits(word)))

        for link in soup.find_all('a'):
            if link:
                # Get each linked url within the page
                linked_url = link.get('href')

                # Join it with the page's url in case its a relative url
                complete_url = urljoin(url, linked_url)

                # Discard the fragment part if there is one
                complete_url = urldefrag(complete_url)[0]

                # Add the new complete url to list of links
                links.append(complete_url)

    except Exception as e:
        # Print an error message if fail to extract links
        print(f"Failed to extract links from url {url}")

    return links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)

        # print(parsed.netloc)

        if parsed.scheme not in set(["http", "https"]):
            return False

        # List of allowed domains for this assignment
        domains = ['ics.uci.edu', 'cs.uci.edu', 'informatics.uci.edu', 'stat.uci.edu']

        # Get the domain of the provided url
        url_domain = parsed.netloc.lower()

        # If the provided url domain is NOT one of the allowed domains, return False
        is_an_allowed_domain = False

        for each_domain in domains:
            if each_domain == url_domain or url_domain.endswith(each_domain):
                is_an_allowed_domain = True
                break
        
        if not is_an_allowed_domain:
            return False
                
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def output_stats():
    # Will be used to output statistics of the crawler
    pass