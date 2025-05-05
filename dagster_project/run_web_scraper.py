from dagster import build_op_context
from web_assets import scrape_website, WebScrapingConfig
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_aibuddy_scraper():
    """Run the web scraper for aibuddy.software"""
    try:
        # Create configuration specific for aibuddy.software
        config = WebScrapingConfig(
            base_url="https://aibuddy.software",
            max_depth=2,  # Depth of 2 to reach PDFs in papers section
            include_images=True,
            include_links=True,
            user_agent="Mozilla/5.0 (compatible; InsightMesh/1.0; +https://insight-mesh.com)",
            rate_limit_delay=1.0  # 1 second delay between requests
        )
        
        # Create context with config
        context = build_op_context(config=config)
        
        # Run the scraping asset
        logger.info("Starting to scrape aibuddy.software...")
        result = scrape_website(context)
        
        # Log results
        logger.info(f"Successfully scraped {len(result['scraped_pages'])} pages")
        
        # Log PDF-specific information
        pdf_pages = [page for page in result["scraped_pages"] 
                    if page.get("content_type", "").lower().startswith("application/pdf")]
        
        logger.info(f"Found {len(pdf_pages)} PDF documents:")
        for pdf in pdf_pages:
            logger.info(f"- {pdf['url']}")
            logger.info(f"  Title: {pdf['title']}")
            logger.info(f"  Pages: {pdf.get('num_pages', 'Unknown')}")
            
    except Exception as e:
        logger.error(f"Error running web scraper: {e}")
        raise

def run_tddbuddy_scraper():
    """Run the web scraper for tddbuddy.com"""
    try:
        # Create configuration specific for tddbuddy.com
        config = WebScrapingConfig(
            base_url="https://tddbuddy.com",
            max_depth=2,  # Set to 2 to reach kata pages at /katas/kata-name.html
            include_images=True,
            include_links=True,
            user_agent="Mozilla/5.0 (compatible; InsightMesh/1.0; +https://insight-mesh.com)",
            rate_limit_delay=1.0  # 1 second delay between requests
        )
        
        # Create context with config
        context = build_op_context(config=config)
        
        # Run the scraping asset
        logger.info("Starting to scrape tddbuddy.com...")
        result = scrape_website(context)
        
        # Log results
        logger.info(f"Successfully scraped {len(result['scraped_pages'])} pages")
        
        # Log kata-specific information
        kata_pages = [page for page in result["scraped_pages"] 
                     if "/katas/" in page.get("url", "")]
        
        logger.info(f"Found {len(kata_pages)} kata pages:")
        for kata in kata_pages:
            logger.info(f"- {kata['url']}")
            logger.info(f"  Title: {kata['title']}")
        
        # Log PDF-specific information
        pdf_pages = [page for page in result["scraped_pages"] 
                    if page.get("content_type", "").lower().startswith("application/pdf")]
        
        logger.info(f"Found {len(pdf_pages)} PDF documents:")
        for pdf in pdf_pages:
            logger.info(f"- {pdf['url']}")
            logger.info(f"  Title: {pdf['title']}")
            logger.info(f"  Pages: {pdf.get('num_pages', 'Unknown')}")
            
    except Exception as e:
        logger.error(f"Error running web scraper: {e}")
        raise

if __name__ == "__main__":
    # Uncomment the scraper you want to run
    # run_aibuddy_scraper()
    run_tddbuddy_scraper() 