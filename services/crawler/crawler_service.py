# services/crawler/crawler_service.py
import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# Define patterns of interest at the module level
PATTERNS_OF_INTEREST = {
    "api_key_generic": r"[aA][pP][iI]_?[kK][eE][yY][\s:=]+['\"]?([a-zA-Z0-9_.-]{20,})['\"]?",
    "secret_key_generic": r"[sS][eE][cC][rR][eE][tT]_?[kK][eE][yY][\s:=]+['\"]?([a-zA-Z0-9_.-]{20,})['\"]?",
    "access_token_generic": r"[aA][cC][cC][eE][sS][sS]_?[tT][oO][kK][eE][nN][\s:=]+['\"]?([a-zA-Z0-9_.-]{20,})['\"]?",
    "client_id_generic": r"[cC][lL][iI][eE][nN][tT]_?[iI][dD][\s:=]+['\"]?([a-zA-Z0-9_.-]{10,})['\"]?",
    "client_secret_generic": r"[cC][lL][iI][eE][nN][tT]_?[sS][eE][cC][rR][eE][tT][\s:=]+['\"]?([a-zA-Z0-9_.-]{20,})['\"]?",
    "aws_access_key_id": r"AKIA[0-9A-Z]{16}",
    "aws_secret_access_key": r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])", # Avoid matching base64 encoded strings
    "google_api_key": r"AIza[0-9A-Za-z\-_]{35}",
    "google_oauth_client_id": r"[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com",
    "firebase_api_key": r"AIza[0-9A-Za-z\-_]{35}", # Same as Google API Key
    "github_token_classic": r"ghp_[0-9a-zA-Z]{36}", # GitHub Personal Access Token (Classic)
    "github_token_fine_grained": r"github_pat_[0-9a-zA-Z_]{82}", # GitHub Personal Access Token (Fine-grained)
    "github_oauth_client_id": r"Iv1\.[0-9a-f]{16}",
    "github_oauth_client_secret": r"[0-9a-f]{40}",
    "ssh_private_key_header": r"-----BEGIN ((RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY)-----",
    "ssh_public_key_full": r"ssh-(rsa|dss|ed25519|ecdsa-sha2-nistp256) AAAA[0-9A-Za-z+/]+[=]{0,3}( [^@]+@[^@]+)?",
    "pgp_private_key_header": r"-----BEGIN PGP PRIVATE KEY BLOCK-----",
    "pgp_public_key_header": r"-----BEGIN PGP PUBLIC KEY BLOCK-----",
    "email_address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "basic_auth_url": r"[a-zA-Z][a-zA-Z0-9+-.]*://[^:]+:[^@]+@[^/?#]+", # Scheme://user:pass@host
    "jwt_token": r"ey[A-Za-z0-9-_=]+\.ey[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*",
    "slack_token_legacy": r"xox[pbar]-[0-9]{10,13}-[0-9]{10,13}-[0-9]{10,13}-[a-fA-F0-9]{32}",
    "slack_webhook_url": r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+",
    "twilio_sid": r"AC[a-f0-9]{32}",
    "twilio_auth_token": r"SK[a-f0-9]{32}", # Can be the same as SID, but often used as auth
    "stripe_api_key": r"sk_live_[0-9a-zA-Z]{24}|pk_live_[0-9a-zA-Z]{24}",
    "paypal_braintree_access_token": r"access_token\$production\$[0-9a-z]{16}\$[0-9a-f]{32}",
    "square_access_token": r"sq0atp-[0-9A-Za-z\-_]{22}",
    "square_oauth_secret": r"sq0csp-[0-9A-Za-z\-_]{43}",
    "generic_password_in_url": r"[a-zA-Z][a-zA-Z0-9+-.]*://[^:]+:([^@]+)@[^/?#]+", # Captures password from user:pass@host
    "url_with_query_params": r"https?://[^\s/$.?#].[^\s]*\?[^\s]*" # Generic URL with query parameters
}

def extract_strings_of_interest(text_content: str, custom_patterns: dict = None) -> dict:
    """
    Extracts strings of interest from text content based on predefined and custom regex patterns.
    """
    if not isinstance(text_content, str):
        return {}
        
    patterns = PATTERNS_OF_INTEREST.copy()
    if custom_patterns:
        patterns.update(custom_patterns)

    found_strings = {}
    for pattern_name, regex_pattern in patterns.items():
        try:
            matches = re.findall(regex_pattern, text_content)
            if matches:
                # If regex has capturing groups, findall returns tuples or list of strings for those groups.
                # We typically want the first capturing group if multiple, or the full match if no groups.
                processed_matches = []
                for match in matches:
                    if isinstance(match, tuple): # Multiple capturing groups
                        # Prioritize non-empty groups; often the first one is what we want.
                        # Or, the pattern should be specific about which group to capture.
                        # For now, taking the first non-empty or just the first if all are empty.
                        captured_group = next((g for g in match if g), match[0] if match else "")
                        processed_matches.append(str(captured_group))
                    else: # Full match or single capturing group
                        processed_matches.append(str(match))
                
                if processed_matches:
                    found_strings[pattern_name] = sorted(list(set(processed_matches)))
        except re.error as e:
            logger.error(f"Regex error for pattern '{pattern_name}': {e}")
            found_strings[pattern_name] = [f"Regex error: {e}"]
            
    return found_strings

def crawl_site(start_url: str, max_depth: int = 2, domain_restriction: bool = True,
               additional_paths: list = None, custom_strings_patterns: dict = None) -> dict:
    """
    Crawls a website starting from start_url up to max_depth.
    """
    if not start_url:
        return {"crawled_pages": {}, "all_discovered_links": [], "error": "Start URL cannot be empty."}

    parsed_start_url = urlparse(start_url)
    base_domain = parsed_start_url.netloc if parsed_start_url.netloc else parsed_start_url.path # Handle file:/// URLs

    urls_to_visit_levels = [set() for _ in range(max_depth + 1)]
    urls_to_visit_levels[0] = {start_url}

    if additional_paths:
        for path in additional_paths:
            urls_to_visit_levels[0].add(urljoin(start_url, path))

    visited_urls = set()
    all_discovered_links_set = set(urls_to_visit_levels[0])
    crawled_data = {}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; PythonCrawler/1.0; +http://www.example.com/bot.html)'
    }

    for current_depth in range(max_depth + 1):
        if not urls_to_visit_levels[current_depth]:
            break # No more URLs to visit at this depth or deeper

        current_level_urls_to_visit = list(urls_to_visit_levels[current_depth]) # Stabilize for iteration
        logger.info(f"Depth {current_depth}: Visiting {len(current_level_urls_to_visit)} URLs.")

        for url_to_crawl in current_level_urls_to_visit:
            if url_to_crawl in visited_urls:
                continue

            visited_urls.add(url_to_crawl)
            page_data = {"url": url_to_crawl, "depth": current_depth, "status": "pending", "content_summary": "", "found_strings": {}, "links_found": 0, "error": None}

            if domain_restriction:
                parsed_current_url = urlparse(url_to_crawl)
                current_domain = parsed_current_url.netloc if parsed_current_url.netloc else parsed_current_url.path
                if current_domain != base_domain:
                    page_data["status"] = "skipped_domain_restriction"
                    page_data["error"] = f"Skipped due to domain restriction (expected {base_domain}, got {current_domain})"
                    crawled_data[url_to_crawl] = page_data
                    continue
            
            try:
                logger.debug(f"Fetching URL: {url_to_crawl}")
                response = requests.get(url_to_crawl, headers=headers, timeout=10, allow_redirects=True)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                
                # Update URL if redirected
                if response.url != url_to_crawl:
                    logger.info(f"URL {url_to_crawl} redirected to {response.url}")
                    url_to_crawl = response.url # Use the final URL
                    visited_urls.add(url_to_crawl) # Add redirected URL to visited to avoid re-crawling
                    page_data["url"] = url_to_crawl # Update page_data with the final URL

                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' not in content_type:
                    page_data["status"] = "skipped_non_html"
                    page_data["error"] = f"Skipped non-HTML content ({content_type})"
                    page_data["content_summary"] = response.text[:500] if response.text else ""
                    crawled_data[url_to_crawl] = page_data
                    continue

                page_content = response.text
                page_data["content_summary"] = page_content[:500] # Store a snippet
                page_data["found_strings"] = extract_strings_of_interest(page_content, custom_strings_patterns)
                page_data["status"] = "success"

                if current_depth < max_depth: # Only find new links if not at max_depth
                    soup = BeautifulSoup(page_content, 'html.parser')
                    links_on_page = []
                    for a_tag in soup.find_all('a', href=True):
                        link = a_tag['href']
                        absolute_link = urljoin(url_to_crawl, link)
                        
                        # Basic clean up of parameters/fragments for discovery uniqueness
                        parsed_link = urlparse(absolute_link)
                        normalized_link = parsed_link._replace(params='', query='', fragment='').geturl()

                        all_discovered_links_set.add(normalized_link)
                        links_on_page.append(normalized_link)
                        
                        if normalized_link not in visited_urls and (current_depth + 1) <= max_depth:
                             urls_to_visit_levels[current_depth + 1].add(normalized_link)
                    page_data["links_found"] = len(links_on_page)


            except requests.exceptions.Timeout:
                logger.warning(f"Timeout fetching {url_to_crawl}")
                page_data["status"] = "error_timeout"
                page_data["error"] = "Request timed out after 10 seconds."
            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP error for {url_to_crawl}: {e}")
                page_data["status"] = "error_http"
                page_data["error"] = str(e)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request exception for {url_to_crawl}: {e}")
                page_data["status"] = "error_request"
                page_data["error"] = str(e)
            except Exception as e:
                logger.error(f"Generic exception processing {url_to_crawl}: {e}", exc_info=True)
                page_data["status"] = "error_generic"
                page_data["error"] = str(e)
            
            crawled_data[url_to_crawl] = page_data

    return {
        "crawled_pages": crawled_data,
        "all_discovered_links": sorted(list(all_discovered_links_set))
    }

if __name__ == '__main__':
    # Basic example usage (for testing purposes)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test extract_strings_of_interest
    sample_text = """
    My API key is API_KEY: 'abc123xyz789_very_long_key_indeed_for_testing'.
    Another one: api_key=supersecretkey_another_example_of_a_long_api_key
    Email me at test@example.com or contact support@example.org.
    AWS Key: AKIAIOSFODNN7EXAMPLE
    Secret: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
    Link: http://user:password123@example.com/path
    -----BEGIN RSA PRIVATE KEY-----
    MIIEogIBAAKCAQEAl...
    -----END RSA PRIVATE KEY-----
    This is not a secret: wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY (already matched as aws_secret_access_key)
    This is just a base64 string: VGhpcyBpcyBhIGJhc2U2NCBzdHJpbmc= 
    And another: UXVpY2sgYnJvd24gZm94IGp1bXBzIG92ZXIgdGhlIGxhenkgZG9nLg==
    """
    found = extract_strings_of_interest(sample_text)
    logger.info("Found strings in sample text:")
    for k, v in found.items():
        logger.info(f"  {k}: {v}")

    # Test crawl_site (requires a live server or mock server for real testing)
    # This example will likely fail or return limited results without a target.
    # Replace with a controllable test URL if possible.
    # test_crawl_url = "http://info.cern.ch/hypertext/WWW/TheProject.html" # A simple, old site
    test_crawl_url = "https://example.com"
    logger.info(f"\nCrawling site: {test_crawl_url}")
    crawl_results = crawl_site(test_crawl_url, max_depth=1, domain_restriction=True)
    
    logger.info(f"Crawled {len(crawl_results['crawled_pages'])} pages.")
    for page_url, page_info in crawl_results['crawled_pages'].items():
        logger.info(f"  URL: {page_url}, Status: {page_info['status']}")
        if page_info['found_strings']:
            logger.info(f"    Found strings: {page_info['found_strings']}")
        if page_info['error']:
            logger.info(f"    Error: {page_info['error']}")
            
    logger.info(f"Discovered {len(crawl_results['all_discovered_links'])} unique links (normalized).")
    # for link in crawl_results['all_discovered_links']:
    #     logger.info(f"  - {link}")

```
