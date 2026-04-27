import re
from urllib.parse import urlparse, urljoin, urldefrag, parse_qs
from bs4 import BeautifulSoup
import lxml
from hashlib import sha256
from collections import defaultdict

# Add global variables here:
unique_urls = set()
num_words_per_url = {}
common_word_frequencies = {}
subdomains = {}

hashes = set()
version_counts = defaultdict(int)

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

def has_informative_content(info):
    words = info.lower().split()
    meaningful_count = 0

    for w in words:
        w = w.strip(".,!?;:\"()[]")
        if w and w not in stopwords:
            meaningful_count += 1

    return meaningful_count > 20   #Threshold but it can be different, just a basic checking of real content

    # Return true if the page has high textual information content, and return false otherwise

# checks for noisy query parameters with long strings and many digits
def has_dynamic_params(query):
    queries = parse_qs(query)

    for values in queries.values():
        for val in values:
            if len(val) > 15 and sum(c.isdigit() for c in val) > 5:
                return True

    return False

# filters based on known trap query and paths
def param_filter(query, path):
    blocked_queries = ['session', 'ssid', 'phpsessid', '_utm', 'ref', 'search']
    blocked_paths = ['timeline', 'login']
    
    if any(keyword in query for keyword in blocked_queries) or any(keyword in path for keyword in blocked_paths) or has_dynamic_params(query):
        return False

    return True

# checks URL length and path depth
def url_length_depth(url, path):
    depth = len([p for p in path.split('/') if p])
    return not (len(url) > 200 or depth > 10)

# detects repeating directory patterns such as /a/a/a and /a/b/a/b/a/b
def has_repeating_paths(path):
    straight_repeat = re.search(r"(.+/)\1{2,}", path)
    pattern_repeat = re.search(r'(/[^/]+)(/.*)?\1\1', path)
    return not bool(straight_repeat or pattern_repeat)

# checks for excessive number of query parameters
def query_checker(query):
    queries = parse_qs(query)
    return not len(queries) > 5

# returns false if a date trap is found
def has_date_trap(path):
    calendar = re.search(r"(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/(19|20)\d\d$", path)
    archive = re.search(r'/\d{4}/\d{2}/', path)
    return not bool(calendar or archive)

# prevents downloading of 5+ versions of a single page
def has_version_trap(path, query):
    queries = parse_qs(query)

    if 'version' in queries:
        version_counts[path] += 1

        if version_counts[path] > 5:
            return False

    return True

# detects CMS traps such as wiki actions, and filters
def cms_pattern_trap(path, query):
    trap_queries = [
        r'action=diff',
        r'action=edit',
        r'action=download',
        r'version=',
        r'from=',
        r'precision=',
        r'filter%5b', # Checks URL-encoded "filter["
        r'filter\['   # Checks unencoded "filter["
    ]

    if any(re.search(pattern, query) for pattern in trap_queries):
        return False

    # Pagination patterns
    if re.search(r'/page/\d+', path):
        return False

    return True

# Return true is the site is a crawler trap, and return false otherwise
def is_a_trap(url, parsed):
    query = parsed.query.lower()
    path = parsed.path.lower()
    
    return not (param_filter(query, path)
                and url_length_depth(url, path)
                and has_repeating_paths(path)
                and query_checker(query)
                and has_date_trap(path)
                and has_version_trap(path, query)
                and cms_pattern_trap(path, query))

def is_page_duplicate(page_text):
    # Return true if the page is a duplicate of a previously crawled page, and return false otherwise

    # Compute the hash of the provided webpage text
    text_to_hash = page_text
    page_hash = sha256(text_to_hash.encode('utf-8')).hexdigest()

    # Check if the hash was already seen
    if page_hash in hashes:
        return True
    else:
        hashes.add(page_hash)
        return False

def is_page_near_duplicate(page_words):
    # Return true if the page is a near duplicate of a previously crawled page, and return false otherwise
    if not page_words:
        return False

    # Compute the fingerprint of the provided webpage words
    curr_fingerprint = simhash(page_words, hasher="xxh3")

    # Define a threshold value
    threshold = 6

    # Check if a near duplicate page already exists using Hamming distance
    for prev_fingerprint in simhash_fingerprints:
        if hamming_distance(curr_fingerprint, prev_fingerprint) < threshold:
            return True

    simhash_fingerprints.add(curr_fingerprint)
    return False

def is_too_large(resp):
    # Return true if the file is too large, and return false otherwise
    if not resp.raw_response or not resp.raw_response.content:
        return 0
    return len(resp.raw_response.content) > 2_000_000 #2MB but still have to check with TA

def word_is_valid(word):
    # Return true if the given word has no digits 0-9, contains letters, etc. Return false otherwise
    if any(char.isdigit() for char in word):
        return False
    if not any(char.isalpha() for char in word):
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

    if is_too_large(resp):
        return links

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

        # Remove all HTML tags that usually don't hold text content
        for non_content_tag in soup(["script", "style", "img", "header", "footer", "nav"]):
            non_content_tag.extract()

        # ...and then get the webpage text
        webpage_text = " ".join(soup.get_text().replace("\n", " ").split())

        #checking for good content
        if not has_informative_content(webpage_text):
            return links

        # If the webpage text is a duplicate of some previous webpage text that was already scraped, then return an empty list
        if is_page_duplicate(webpage_text):
            return links

        # Collect all the words from the webpage INCLUDING stopwords for right now
        pattern = r"\b\S+\b"
        all_words = re.findall(pattern, webpage_text.lower())
        all_words = list((word for word in all_words if word_is_valid(word)))

        # Defragmenting the current URL once for tracking below
        defragged_url = urldefrag(url)[0]

        # Track unique url
        unique_urls.add(defragged_url)

        # Track word count per webpage INCLUDING stopwords
        num_words_per_url[defragged_url] = len(all_words)

        # Increasing the count of global frequency of each word in the webpage EXCLUDING stopwords
        for word in all_words:
            if word not in stopwords:
                common_word_frequencies[word] = common_word_frequencies.get(word, 0) + 1

        # For every successfully scraped webpage it records which subdomain it belongs to and adds its URL to that subdomain's dictionary 
        parsed_url = urlparse(defragged_url)
        netloc = parsed_url.netloc.lower()
        if netloc.endswith('.uci.edu'):
            if netloc not in subdomains:
                subdomains[netloc] = 0
            subdomains[netloc] += 1

        # Store all words EXCLUDING stopwords
        content_words_no_stopwords = [word for word in all_words if word not in stopwords]

        for link in soup.find_all('a'):
            if link:
                # Get each linked url within the webpage
                linked_url = link.get('href')
                if not linked_url:
                    continue

                # Join it with the webpage's url in case its a relative url
                complete_url = urljoin(url, linked_url)

                # Discard the fragment part if there is one
                complete_url = urldefrag(complete_url)[0]

                # Add the new complete url to list of links
                if complete_url:
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

        if is_a_trap(url, parsed):
            return False
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

def output_stats(filepath="report.txt"):
    # Will be used to output statistics of the crawler
    with open(filepath, "w") as f:

        f.write("CRAWL STATISTICS\n\n")

        # Unique webpages
        f.write(f"Total unique pages crawled: {len(unique_urls)}\n\n")

        # Longest webpage by word count
        if num_words_per_url:
            longest_url = max(num_words_per_url, key=num_words_per_url.get)
            f.write(f"Longest page: {longest_url}\n")
            f.write(f"Word count: {num_words_per_url[longest_url]}\n\n")
        else:
            f.write("No pages crawled yet.\n\n")

        # Top 50 most common words, no stopwords
        f.write("Top 50 most common words (stopwords excluded):\n")
        sorted_words = sorted(common_word_frequencies.items(), key=lambda x: x[1], reverse=True)
        for rank, (word, freq) in enumerate(sorted_words[:50], start=1):
            f.write(f"{rank:>2}. {word} ({freq})\n")
        f.write("\n")

        # Subdomains in alphabetical order
        f.write("Subdomains found:\n")
        for subdomain in sorted(subdomains.keys()):
            f.write(f"{subdomain}, {subdomains[subdomain]}\n")
