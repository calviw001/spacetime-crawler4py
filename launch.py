from configparser import ConfigParser
from argparse import ArgumentParser

from utils.server_registration import get_cache_server
from utils.config import Config
from crawler import Crawler
import scraper
import time

def output_stats(filepath="report.txt"):
    # Outputs statistics of the crawler
    with open(filepath, "w") as f:
 
        f.write("CRAWL STATISTICS\n\n")
 
        # Unique pages 
        f.write(f"Total unique pages crawled: {len(scraper.unique_urls)}\n\n")
 
        # Longest page by word count 
        if scraper.num_words_per_url:
            longest_url = max(scraper.num_words_per_url, key=scraper.num_words_per_url.get)
            f.write(f"Longest page: {longest_url}\n")
            f.write(f"Word count: {scraper.num_words_per_url[longest_url]}\n\n")
        else:
            f.write("No pages crawled yet.\n\n")
 
        # Top 50 most common words, no stopwords 
        f.write("Top 50 most common words (stopwords excluded):\n")
        sorted_words = sorted(scraper.common_word_frequencies.items(), key=lambda x: x[1], reverse=True)
        for rank, (word, freq) in enumerate(sorted_words[:50], start=1):
            f.write(f"{rank:>2}. {word} ({freq})\n")
        f.write("\n")
 
        # Subdomains in alphabetical order
        f.write("Subdomains found:\n")
        for subdomain in sorted(scraper.subdomains.keys()):
            f.write(f"{subdomain}, {scraper.subdomains[subdomain]}\n")
        f.write("\n")

        #Total Runtime
        hrs = int(total_runtime // 36000)
        mins = int((total_runtime % 36000) // 60)
        secs = total_runtime % 60
        f.write(f"Runtime: {hrs}h {mins}m {secs:.2f}s")

def main(config_file, restart):
    global total_runtime
    cparser = ConfigParser()
    cparser.read(config_file)
    config = Config(cparser)
    config.cache_server = get_cache_server(config, restart)
    crawler = Crawler(config, restart)
    start_time = time.perf_counter()
    try:
        crawler.start()
    except KeyboardInterrupt:
        print("keyboard interrupt")
    finally:
        end_time = time.perf_counter()
        total_runtime = end_time - start_time
        output_stats("report.txt")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--restart", action="store_true", default=False)
    parser.add_argument("--config_file", type=str, default="config.ini")
    args = parser.parse_args()
    main(args.config_file, args.restart)
