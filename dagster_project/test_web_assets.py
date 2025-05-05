import logging
from dagster import build_op_context
from web_assets import scrape_website, WebScrapingConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_web_scraping():
    """Test the web scraping functionality including PDF handling."""
    try:
        logger.info("Testing web scraping with PDF support...")
        
        # Create configuration with depth 2 to reach PDFs in papers section
        config = WebScrapingConfig(
            base_url="https://aibuddy.software/",
            max_depth=2,  # Increased depth to reach PDFs
            include_images=True,
            include_links=True
        )
        
        # Create context with config
        context = build_op_context(config=config)
        
        # Run the asset
        result = scrape_website(context)
        
        # Log PDF-specific information
        pdf_pages = [page for page in result["scraped_pages"] 
                    if page.get("content_type", "").lower().startswith("application/pdf")]
        
        logger.info(f"Total pages scraped: {len(result['scraped_pages'])}")
        logger.info(f"PDFs found: {len(pdf_pages)}")
        
        for pdf in pdf_pages:
            logger.info(f"PDF: {pdf['url']}")
            logger.info(f"  Title: {pdf['title']}")
            logger.info(f"  Author: {pdf.get('author', 'Unknown')}")
            logger.info(f"  Pages: {pdf.get('num_pages', 'Unknown')}")
            logger.info(f"  Extraction Method: {pdf.get('extraction_method', 'Unknown')}")
            logger.info(f"  Content Length: {len(pdf.get('content', ''))} characters")
        
    except Exception as e:
        logger.error(f"Error during web scraping test: {str(e)}")

if __name__ == "__main__":
    test_web_scraping() 