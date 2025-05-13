import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from .client import WebClient
from .neo4j_service import WebNeo4jService
from .elastic_service import WebElasticsearchService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    """Scraper for web content using client and service classes."""
    
    def __init__(
        self,
        base_url: str,
        max_depth: int = 2,
        include_images: bool = True,
        include_links: bool = True,
        user_agent: str = "Mozilla/5.0 (compatible; InsightMesh/1.0; +https://insightmesh.com)",
        rate_limit_delay: float = 1.0
    ):
        self.base_url = base_url
        self.max_depth = max_depth
        self.include_images = include_images
        self.include_links = include_links
        self.client = WebClient(user_agent, rate_limit_delay)
        self.neo4j = WebNeo4jService()
        self.es = WebElasticsearchService()
        self.logger = logging.getLogger(__name__)
        self.processed_urls = set()
        self.scraped_pages = []
        self.all_links = []
        self.all_images = []

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract and validate links from the page."""
        links = []
        
        # First, look for navigation menus
        nav_links = soup.find_all(['nav', 'ul', 'li'], class_=['nav', 'dropdown', 'menu'])
        for nav in nav_links:
            for a in nav.find_all("a", href=True):
                href = a["href"]
                if href.startswith("#"):
                    continue
                try:
                    normalized_url = self.client.normalize_url(href, base_url)
                    if self.client.is_same_domain(normalized_url, self.base_url):
                        link_data = {
                            "url": normalized_url,
                            "text": a.get_text(strip=True),
                            "is_valid": True
                        }
                        if link_data not in links:
                            links.append(link_data)
                            if link_data not in self.all_links:
                                self.all_links.append(link_data)
                except Exception as e:
                    self.logger.warning(f"Error parsing URL {href}: {e}")
        
        # Then look for all other links on the page
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#"):
                continue
            try:
                normalized_url = self.client.normalize_url(href, base_url)
                if self.client.is_same_domain(normalized_url, self.base_url):
                    link_data = {
                        "url": normalized_url,
                        "text": a.get_text(strip=True),
                        "is_valid": True
                    }
                    if link_data not in links:
                        links.append(link_data)
                        if link_data not in self.all_links:
                            self.all_links.append(link_data)
            except Exception as e:
                self.logger.warning(f"Error parsing URL {href}: {e}")
        
        return links

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract and validate images from the page."""
        images = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            try:
                normalized_url = self.client.normalize_url(src, base_url)
                if normalized_url.startswith(("http://", "https://")):
                    image_data = {
                        "url": normalized_url,
                        "alt": img.get("alt", ""),
                        "is_valid": True
                    }
                    images.append(image_data)
                    if image_data not in self.all_images:
                        self.all_images.append(image_data)
            except Exception as e:
                self.logger.warning(f"Error parsing image URL {src}: {e}")
        return images

    def scrape_page(self, url: str, depth: int = 0) -> Dict[str, Any]:
        """Scrape a single page and its content."""
        if url in self.processed_urls:
            return {}
            
        # Remove fragment from URL if present
        url = url.split('#')[0]
            
        # Calculate depth based on URL structure
        parsed_url = urlparse(url)
        base_path = urlparse(self.base_url).path.rstrip('/')
        url_path = parsed_url.path.rstrip('/')
        
        # Remove the base path from the URL path to get the relative path
        if url_path.startswith(base_path):
            url_path = url_path[len(base_path):].lstrip('/')
        
        # Calculate depth based on path segments
        path_segments = [s for s in url_path.split('/') if s]
        current_depth = len(path_segments)
        
        if current_depth > self.max_depth:
            return {}
            
        self.processed_urls.add(url)
        self.logger.info(f"Scraping page: {url} (depth: {current_depth})")
        
        try:
            response = self.client.get_page(url)
            if not response:
                return {}
            
            content_type = response.headers.get("Content-Type", "").lower()
            
            if "application/pdf" in content_type:
                # Handle PDF content
                pdf_data = self.client.extract_pdf_content(response)
                metadata = {
                    "url": url,
                    "title": pdf_data["title"] or url.split("/")[-1],
                    "content": pdf_data["content"],
                    "depth": current_depth,
                    "links": [],
                    "images": [],
                    "timestamp": response.headers.get("Last-Modified", ""),
                    "content_type": content_type,
                    "author": pdf_data["author"],
                    "num_pages": pdf_data["num_pages"],
                    "extraction_method": pdf_data["extraction_method"]
                }
            else:
                # Handle HTML content
                soup = self.client.parse_html(response)
                if not soup:
                    return {}
                    
                title = soup.title.string if soup.title else ""
                content = soup.get_text(strip=True)
                
                metadata = {
                    "url": url,
                    "title": title,
                    "content": content,
                    "depth": current_depth,
                    "links": self._extract_links(soup, url) if self.include_links else [],
                    "images": self._extract_images(soup, url) if self.include_images else [],
                    "timestamp": response.headers.get("Last-Modified", ""),
                    "content_type": content_type,
                }

            # Store in Neo4j
            self.neo4j.create_or_update_page(
                metadata,
                relationships=[
                    {
                        "source_url": url,
                        "target_url": link["url"],
                        "properties": {"text": link["text"]}
                    }
                    for link in metadata["links"]
                ]
            )

            # Store in Elasticsearch
            self.es.index_page(metadata)

            # Store images
            for image in metadata["images"]:
                self.neo4j.create_or_update_image(image, url)
                self.es.index_image(image, url)

            # Add to scraped pages
            self.scraped_pages.append(metadata)
            
            # Recursively scrape linked pages
            for link in metadata["links"]:
                next_url = link["url"].split('#')[0]
                if next_url not in self.processed_urls:
                    self.scrape_page(next_url)

            return metadata

        except Exception as e:
            self.logger.error(f"Error scraping page {url}: {e}")
            return {}

    def scrape_site(self) -> Dict[str, Any]:
        """Scrape the entire site starting from the base URL."""
        self.logger.info(f"Starting to scrape site: {self.base_url}")
        
        # Reset tracking variables
        self.scraped_pages = []
        self.all_links = []
        self.all_images = []
        
        try:
            # Start scraping from base URL
            self.scrape_page(self.base_url)
            
            self.logger.info(f"Completed scraping site: {self.base_url}")
            
            # Return aggregated results
            return {
                "scraped_pages": self.scraped_pages,
                "all_links": self.all_links,
                "all_images": self.all_images
            }
        finally:
            # Clean up connections
            self.neo4j.close() 