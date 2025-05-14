from dagster import Definitions, define_asset_job, ScheduleDefinition
from web_assets import (
    scrape_website,
    web_scraping_job,
    web_scraping_schedule
)

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

# Create definitions
defs = Definitions(
    assets=[scrape_website],
    schedules=[web_schedule],
    jobs=[web_job]
) 