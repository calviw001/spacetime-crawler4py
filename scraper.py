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
subdomains = defaultdict(set)

hashes = set()
version_counts = defaultdict(int)
page_counts = defaultdict(int)

stopwords = set([
    "a", "about", "above", "after", "again", "against", "all", "am",
    "an", "and", "any", "are", "aren't", "as", "at", "be", "because",
    "been", "before", "being", "below", "between", "both", "but",
    "by", "can't", "cannot", "could", "couldn't", "did", "didn't",
    "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll",
    "he's", "her", "here", "here's", "hers", "herself", "him",
    "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm",
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its",
    "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd",
    "we'll", "we're", "we've", "were", "weren't", "what", "what's",
    "when", "when's", "where", "where's", "which", "while", "who",
    "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves"
])

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def has_informative_content(info):
    # Return true if the page has high textual information content, and return false otherwise
    words = info.lower().split()
    meaningful_count = 0

    for w in words:
        w = w.strip(".,!?;:\"()[]")
        if w and w not in stopwords:
            meaningful_count += 1

    return meaningful_count > 20 
    
# filters based on known trap query and paths
def param_filter(query, path):
    blocked_queries = ['session', 'ssid', 'phpsessid', 'sid', 'jsessionid'] 
    blocked_paths = ['/login', '/private', '/raw-attachment/', '/zip-attachment/', '/wp-admin', '/phpmyadmin']

    if any(keyword in query for keyword in blocked_queries) or any(keyword in path for keyword in blocked_paths): 
        return False

    return True

# checks URL length and path depth
def url_length_depth(url, path):
    depth = len([p for p in path.split('/') if p])
    return not (len(url) > 300 or depth > 40) 

# detects repeating directory patterns such as /a/a/a and /a/b/a/b/a/b
def has_repeating_paths(path):
    '''straight_repeat = re.search(r"(.+/)\1{2,}", path)
    pattern_repeat = re.search(r'(/[^/]+)(/.*)?\1\1', path)
    return not bool(straight_repeat or pattern_repeat)'''
    parts = path.split('/')
    if any(parts[i] == parts[i+1] == parts[i+2] == parts[i+3] for i in range(len(parts)-2)):
        return False

    return True

# checks for excessive number of query parameters
def query_checker(query):
    queries = parse_qs(query)
    return not len(queries) > 15

# returns true if a no date trap is found
def has_date_trap(path):
    calendar = re.search(r"(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/(19|20)\d\d$", path)
    return not bool(calendar)

# prevents downloading of many variants of a single page
def variants_trap(path, query):
    queries = parse_qs(query)

    if 'version' in queries:
        version_counts[path] += 1

        if version_counts[path] > 30:
            return False

    base_path = re.sub(r'/page/\d+', '', path)
    if re.search(r'/page/\d+', path):
        page_counts[base_path] += 1

        if page_counts[base_path] > 30:
            return False
    
    return True

# detects CMS traps such as wiki actions, and filters
def cms_pattern_trap(path, query):
    trap_queries = [
        r'action=diff',
        r'action=edit',
        r'action=download'
    ]

    if any(re.search(pattern, query) for pattern in trap_queries):
        return False

    return True

# Return true is the site is a crawler trap, and return false otherwise
def is_a_trap(url, parsed):
    try:
        query = parsed.query.lower()
        path = parsed.path.lower()

        return not (param_filter(query, path)
                    and url_length_depth(url, path) 
                    and has_repeating_paths(path)
                    and query_checker(query) 
                    and has_date_trap(path)
                    and variants_trap(path, query)
                    and cms_pattern_trap(path, query))

    except Exception as e:
        # If parsing fails for some reason, 'maybe' trap
        print(f"Maybe trap, failed for this {url}: {e}")
        return True

def is_page_duplicate(page_text):
    # Return true if the webpage is a duplicate of a previously crawled webpage, and return false otherwise

    # Compute the hash of the provided webpage text
    page_hash = sha256(page_text.encode('utf-8')).hexdigest()
    
    # Check if the hash was already seen
    if page_hash in hashes:
        return True
    else:
        hashes.add(page_hash)
        return False

def is_too_large(resp):
    # Return true if the file is too large, and return false otherwise
    if not resp.raw_response or not resp.raw_response.content:
        return False
    return len(resp.raw_response.content) > 10 * 1024**2

def word_is_valid(word):
    # Return true if the given word has no digits 0-9, contains letters, or is only a single character. Return false otherwise
    if any(char.isdigit() for char in word):
        return False

    if not any(char.isalpha() for char in word):
        return False

    if len(word) < 2 and word.lower() not in ['a', 'i', 'o']:  # A, I, and O are the only words that are a single character long.
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
    links = set()

    # Return an empty list if there is no webpage content
    if not resp.raw_response or not resp.raw_response.content:
        return links

    # Return an empty list if the response is too large
    if is_too_large(resp):
        return links

    # Explicity return an empty links for additional status codes!:
    if resp.status in {400, 401, 402, 403, 404, 600, 601, 602, 603, 604, 605, 607, 608}:
        return links

    # Continue with the function if the status code is 200, and return an empty list if it is not 200
    if resp.status == 200:
        pass  # process normally
    else:
        return links

    # Get the webpage content
    page_content = resp.raw_response.content

    # Get the encoding from the raw response
    encoding = resp.raw_response.encoding 

    # If encoding equals None, then default to utf-8 because that's the most common encoding used 
    if not encoding:
        encoding = 'utf-8'

    try:
        # Try decoding the bytes using the encoding provided from the raw response
        decoded = page_content.decode(encoding)

    except (UnicodeDecodeError, LookupError):
        # If the bytes failed to match the encoding, or the encoding name was unrecognized...
        try:
            # ...then try to fallback to using utf-8 with forgiveness...
            decoded = page_content.decode('utf-8', errors='replace')
        except Exception:
            # ...and then try to to use Latin-1 with forgiveness as a last resort.
            decoded = page_content.decode('latin-1', errors='replace')

    try:
        soup = BeautifulSoup(decoded, 'lxml')
        
        # Remove all HTML tags that usually don't hold text content
        for non_content_tag in soup(["script", "style", "img", "header", "footer", "nav"]):
            non_content_tag.extract()

        # ...and then get the webpage text
        webpage_text = " ".join(soup.get_text().replace("\n", " ").split())

        # Generate statistics for the webpages IF the webpage has informative content AND isn't a duplicate
        if has_informative_content(webpage_text) and not is_page_duplicate(webpage_text):

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
                subdomains[netloc].add(defragged_url)

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
                    links.add(complete_url)

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
            # Example: cecs.uci.edu.endswith(cs.uci.edu) is True which is not what we want! 
            # Fix it by requiring a dot before the domain!
            if each_domain == url_domain or url_domain.endswith('.' + each_domain):
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
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|txt|log|md|rst)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise
