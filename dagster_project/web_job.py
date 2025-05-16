from dagster import Definitions, define_asset_job, ScheduleDefinition, fs_io_manager, IOManager, OutputContext, InputContext
import json
import os
from typing import Any, Dict
from web_assets import (
    scrape_website,
    web_scraping_job,
    web_scraping_schedule
)

class WebScrapingIOManager(IOManager):
    """Custom IO manager for web scraping data that handles serialization safely."""
    
    def handle_output(self, context: OutputContext, obj: Any) -> None:
        """Handle the output by safely serializing the data."""
        if obj is None:
            return
            
        # Create a simplified version of the data that can be safely serialized
        serializable_data = {
            "scraped_pages": [
                {
                    "url": page.get("url", ""),
                    "title": page.get("title", ""),
                    "content": page.get("content", ""),
                    "metadata": {
                        "images": len(page.get("images", [])),
                        "links": len(page.get("links", [])),
                        "timestamp": page.get("timestamp", "")
                    }
                }
                for page in obj.get("scraped_pages", [])
            ],
            "all_links": list(obj.get("all_links", set())),
            "all_images": list(obj.get("all_images", set())),
            "status": obj.get("status", "unknown")
        }
        
        # Write to file using fs_io_manager's path
        filepath = os.path.join(context.step_context.run_id, f"{context.name}.json")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, "w") as f:
            json.dump(serializable_data, f)
            
    def load_input(self, context: InputContext) -> Dict[str, Any]:
        """Load the input from the serialized data."""
        filepath = os.path.join(context.upstream_output.run_id, f"{context.upstream_output.name}.json")
        
        if not os.path.exists(filepath):
            return None
            
        with open(filepath, "r") as f:
            return json.load(f)

# Define the web scraping job
web_job = define_asset_job(
    name="web_job",
    selection=[scrape_website]
)

# Define schedule
web_schedule = ScheduleDefinition(
    job=web_job,
    cron_schedule="0 */12 * * *"  # Run every 12 hours
)

# Create definitions with custom IO manager
defs = Definitions(
    assets=[scrape_website],
    schedules=[web_schedule],
    jobs=[web_job],
    resources={"io_manager": WebScrapingIOManager()}
) 