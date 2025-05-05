import os
import logging
import hashlib
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
import PyPDF2
from io import BytesIO
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfparser import PDFSyntaxError
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraperConfig:
    """Configuration for web scraping."""
    def __init__(
        self,
        base_url: str,
        max_depth: int = 2,
        include_images: bool = True,
        include_links: bool = True,
        user_agent: str = "Mozilla/5.0 (compatible; InsightMesh/1.0; +https://insight-mesh.com)",
        rate_limit_delay: float = 1.0
    ):
        self.base_url = base_url
        self.max_depth = max_depth
        self.include_images = include_images
        self.include_links = include_links
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay

class WebScraper:
    def __init__(
        self,
        config: WebScraperConfig,
        neo4j_service: Optional[Any] = None,
        elastic_service: Optional[Any] = None
    ):
        self.config = config
        self.neo4j = neo4j_service or self._init_neo4j()
        self.es = elastic_service or self._init_elasticsearch()
        self.logger = logging.getLogger(__name__)
        self.processed_urls = set()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})
        self.scraped_pages = []
        self.all_links = []
        self.all_images = []

    def _init_neo4j(self):
        return GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
        )

    def _init_elasticsearch(self):
        return Elasticsearch(
            [
                {
                    "scheme": "http",
                    "host": os.getenv("ELASTICSEARCH_HOST", "localhost"),
                    "port": int(os.getenv("ELASTICSEARCH_PORT", "9200")),
                }
            ]
        )

    def _generate_document_id(self, url: str) -> str:
        """Generate a unique document ID for Elasticsearch."""
        return hashlib.md5(url.encode()).hexdigest()

    def _store_in_neo4j(self, data: Dict[str, Any], node_type: str, relationships: Optional[List[Dict[str, Any]]] = None):
        """Store data in Neo4j with relationships."""
        try:
            with self.neo4j.session() as session:
                # Create or update node
                query = f"""
                MERGE (n:{node_type} {{url: $url}})
                SET n += $properties
                RETURN n
                """
                properties = {
                    "url": data["url"],
                    "title": data["title"],
                    "content_type": data["content_type"],
                    "timestamp": data["timestamp"]
                }
                
                # Add num_pages for PDF files
                if data.get("content_type", "").lower().startswith("application/pdf"):
                    properties["num_pages"] = data.get("num_pages", 0)
                
                result = session.run(query, url=data["url"], properties=properties)
                self.logger.info(f"Stored {node_type} node with URL {data['url']}")

                # Create relationships if specified
                if relationships:
                    for rel in relationships:
                        try:
                            rel_query = f"""
                            MATCH (source:{rel['source_type']} {{url: $source_url}})
                            MATCH (target:{rel['target_type']} {{url: $target_url}})
                            MERGE (source)-[r:{rel['type']}]->(target)
                            SET r += $properties
                            """
                            session.run(
                                rel_query,
                                source_url=rel["source_url"],
                                target_url=rel["target_url"],
                                properties=rel.get("properties", {})
                            )
                        except Exception as e:
                            self.logger.warning(f"Error creating relationship: {e}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing {node_type} in Neo4j: {e}")
            raise

    def _store_in_elasticsearch(self, data: Dict[str, Any], index: str):
        """Store data in Elasticsearch."""
        try:
            doc_id = self._generate_document_id(data["url"])
            result = self.es.index(index=index, id=doc_id, document=data)
            self.logger.info(f"Stored document in {index} with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error storing document in Elasticsearch: {e}")
            raise

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract and validate links from the page."""
        links = []
        
        # First, look for navigation menus
        nav_links = soup.find_all(['nav', 'ul', 'li'], class_=['nav', 'dropdown', 'menu'])
        for nav in nav_links:
            for a in nav.find_all("a", href=True):
                href = a["href"]
                # Skip anchor links
                if href.startswith("#"):
                    continue
                try:
                    # Handle relative URLs
                    if href.startswith("/"):
                        href = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{href}"
                    elif not href.startswith(("http://", "https://")):
                        # Handle relative paths without leading slash
                        base_path = urlparse(base_url).path
                        if base_path.endswith("/"):
                            href = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{base_path}{href}"
                        else:
                            href = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{base_path.rsplit('/', 1)[0]}/{href}"

                    parsed = urlparse(href)
                    if parsed.netloc == urlparse(base_url).netloc:  # Only include internal links
                        link_data = {
                            "url": href,
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
            # Skip anchor links
            if href.startswith("#"):
                continue
            try:
                # Handle relative URLs
                if href.startswith("/"):
                    href = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{href}"
                elif not href.startswith(("http://", "https://")):
                    # Handle relative paths without leading slash
                    base_path = urlparse(base_url).path
                    if base_path.endswith("/"):
                        href = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{base_path}{href}"
                    else:
                        href = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{base_path.rsplit('/', 1)[0]}/{href}"

                parsed = urlparse(href)
                if parsed.netloc == urlparse(base_url).netloc:  # Only include internal links
                    link_data = {
                        "url": href,
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
                # Handle relative URLs
                if src.startswith("/"):
                    src = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{src}"
                elif not src.startswith(("http://", "https://")):
                    continue

                image_data = {
                    "url": src,
                    "alt": img.get("alt", ""),
                    "is_valid": True
                }
                images.append(image_data)
                if image_data not in self.all_images:
                    self.all_images.append(image_data)
            except Exception as e:
                self.logger.warning(f"Error parsing image URL {src}: {e}")
        return images

    def _extract_pdf_content(self, response: requests.Response) -> Dict[str, Any]:
        """Extract content from a PDF file using Python libraries."""
        try:
            # First try with PyPDF2
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from all pages
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            # Get metadata
            metadata = pdf_reader.metadata or {}
            
            return {
                "content": text_content,
                "title": metadata.get("/Title", ""),
                "author": metadata.get("/Author", ""),
                "num_pages": len(pdf_reader.pages),
                "extraction_method": "PyPDF2"
            }
        except Exception as e:
            self.logger.warning(f"PyPDF2 extraction failed, trying pdfminer.six: {e}")
            try:
                # Fallback to pdfminer.six
                pdf_file = BytesIO(response.content)
                text_content = pdfminer_extract_text(pdf_file)
                
                # Try to get basic metadata from PyPDF2 even if text extraction failed
                try:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    metadata = pdf_reader.metadata or {}
                    num_pages = len(pdf_reader.pages)
                except:
                    metadata = {}
                    num_pages = 0
                
                return {
                    "content": text_content,
                    "title": metadata.get("/Title", ""),
                    "author": metadata.get("/Author", ""),
                    "num_pages": num_pages,
                    "extraction_method": "pdfminer.six"
                }
            except (PDFSyntaxError, Exception) as pdfminer_error:
                self.logger.error(f"PDF extraction failed with both methods: {pdfminer_error}")
                return {
                    "content": "",
                    "title": "",
                    "author": "",
                    "num_pages": 0,
                    "extraction_method": "failed"
                }

    def scrape_page(self, url: str, depth: int = 0) -> Dict[str, Any]:
        """Scrape a single page and its content."""
        if url in self.processed_urls:
            return {}
            
        # Remove fragment from URL if present
        url = url.split('#')[0]
            
        # Calculate depth based on URL structure
        parsed_url = urlparse(url)
        base_path = urlparse(self.config.base_url).path.rstrip('/')
        url_path = parsed_url.path.rstrip('/')
        
        # Remove the base path from the URL path to get the relative path
        if url_path.startswith(base_path):
            url_path = url_path[len(base_path):].lstrip('/')
        
        # Calculate depth based on path segments
        path_segments = [s for s in url_path.split('/') if s]
        current_depth = len(path_segments)
        
        if current_depth > self.config.max_depth:
            return {}
            
        self.processed_urls.add(url)
        self.logger.info(f"Scraping page: {url} (depth: {current_depth})")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            
            if "application/pdf" in content_type:
                # Handle PDF content
                pdf_data = self._extract_pdf_content(response)
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
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string if soup.title else ""
                content = soup.get_text(strip=True)
                
                metadata = {
                    "url": url,
                    "title": title,
                    "content": content,
                    "depth": current_depth,
                    "links": self._extract_links(soup, url) if self.config.include_links else [],
                    "images": self._extract_images(soup, url) if self.config.include_images else [],
                    "timestamp": response.headers.get("Last-Modified", ""),
                    "content_type": content_type,
                }

            # Store in Neo4j
            self._store_in_neo4j(
                metadata,
                "WebPage",
                relationships=[
                    {
                        "source_type": "WebPage",
                        "source_url": url,
                        "target_type": "WebPage",
                        "target_url": link["url"],
                        "type": "LINKS_TO",
                        "properties": {"text": link["text"]}
                    }
                    for link in metadata["links"]
                ]
            )

            # Store in Elasticsearch
            self._store_in_elasticsearch(metadata, "web_pages")

            # Add to scraped pages
            self.scraped_pages.append(metadata)
            
            # Recursively scrape linked pages
            for link in metadata["links"]:
                self.scrape_page(link["url"])

            return metadata

        except Exception as e:
            self.logger.error(f"Error scraping page {url}: {e}")
            return {}

    def scrape_site(self) -> Dict[str, Any]:
        """Scrape the entire site starting from the base URL."""
        self.logger.info(f"Starting to scrape site: {self.config.base_url}")
        
        # Reset tracking variables
        self.scraped_pages = []
        self.all_links = []
        self.all_images = []
        
        # Start scraping from base URL
        self.scrape_page(self.config.base_url)
        
        self.logger.info(f"Completed scraping site: {self.config.base_url}")
        
        # Return aggregated results
        return {
            "scraped_pages": self.scraped_pages,
            "all_links": self.all_links,
            "all_images": self.all_images
        } 