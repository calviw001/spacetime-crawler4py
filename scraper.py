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

hashes = set() # sha256

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

def is_page_duplicate(page_text):
    # Return true if the webage is a duplicate of a previously crawled webpage, and return false otherwise

    # Compute the hash of the provided webpage text
    page_hash = sha256(page_text.encode('utf-8')).hexdigest()
    
    # Check if the hash was already seen
    if page_hash in hashes:
        return True
    else:
        hashes.add(page_hash)
        return False

def is_too_large():
    # Return true if the file is too large, and return false otherwise
    pass

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

    # Return an empty list if the status code is not 200
    if resp.status != 200:
        return links

    # Return an empty list if there is no webpage content
    if not resp.raw_response or not resp.raw_response.content:
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
