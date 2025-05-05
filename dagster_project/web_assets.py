import logging
from dagster import asset, AssetExecutionContext, Config, Definitions, ScheduleDefinition, define_asset_job
from web_scraper import WebScraper, WebScraperConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScrapingConfig(Config):
    """Configuration for web scraping assets."""
    base_url: str
    max_depth: int = 1
    include_images: bool = True
    include_links: bool = True
    user_agent: str = "Mozilla/5.0 (compatible; InsightMesh/1.0; +https://insightmesh.com)"
    rate_limit_delay: float = 1.0

@asset
def scrape_website(context: AssetExecutionContext):
    """Asset to scrape a website and store its content in Neo4j and Elasticsearch."""
    try:
        config = context.op_config
        
        # Initialize the web scraper
        scraper = WebScraper(config)
        
        # Start scraping from the base URL
        result = scraper.scrape_site()
        
        # Add metadata about the scraping process
        context.add_output_metadata({
            "pages_scraped": len(result["scraped_pages"]),
            "total_links": len(result["all_links"]),
            "total_images": len(result["all_images"]),
            "status": "success"
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Error during web scraping: {str(e)}")
        context.add_output_metadata({
            "status": "error",
            "error_message": str(e)
        })
        raise

# Define the job
web_scraping_job = define_asset_job(
    name="web_scraping_job",
    selection=[scrape_website]
)

# Define a schedule to run every day at midnight
web_scraping_schedule = ScheduleDefinition(
    job=web_scraping_job,
    cron_schedule="0 0 * * *"  # Run daily at midnight
)

# Create definitions object
defs = Definitions(
    assets=[scrape_website],
    schedules=[web_scraping_schedule],
    jobs=[web_scraping_job]
) 