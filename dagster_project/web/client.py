import logging
import requests
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import PyPDF2
from io import BytesIO
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfparser import PDFSyntaxError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebClient:
    """Client for handling HTTP requests and basic web operations."""
    
    def __init__(
        self,
        user_agent: str = "Mozilla/5.0 (compatible; InsightMesh/1.0; +https://insightmesh.com)",
        rate_limit_delay: float = 1.0
    ):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.rate_limit_delay = rate_limit_delay
        self.logger = logging.getLogger(__name__)

    def get_page(self, url: str) -> Optional[requests.Response]:
        """Get a page and handle rate limiting."""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None

    def parse_html(self, response: requests.Response) -> Optional[BeautifulSoup]:
        """Parse HTML content from a response."""
        try:
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            self.logger.error(f"Error parsing HTML: {e}")
            return None

    def extract_pdf_content(self, response: requests.Response) -> Dict[str, Any]:
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

    def normalize_url(self, url: str, base_url: str) -> str:
        """Normalize a URL relative to a base URL."""
        try:
            if url.startswith("/"):
                return f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{url}"
            elif not url.startswith(("http://", "https://")):
                base_path = urlparse(base_url).path
                if base_path.endswith("/"):
                    return f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{base_path}{url}"
                else:
                    return f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{base_path.rsplit('/', 1)[0]}/{url}"
            return url
        except Exception as e:
            self.logger.error(f"Error normalizing URL {url}: {e}")
            return url

    def is_same_domain(self, url: str, base_url: str) -> bool:
        """Check if a URL belongs to the same domain as the base URL."""
        try:
            return urlparse(url).netloc == urlparse(base_url).netloc
        except Exception as e:
            self.logger.error(f"Error checking domain for URL {url}: {e}")
            return False 