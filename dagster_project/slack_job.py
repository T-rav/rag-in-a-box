from dagster import Definitions, define_asset_job, ScheduleDefinition
from slack_assets import (
    slack_channel_info,
    slack_users,
    scrape_slack_content
)

# Define the Slack job
slack_job = define_asset_job(
    name="slack_job",
    selection=[slack_channel_info, slack_users, scrape_slack_content]
)

# Define schedule
slack_schedule = ScheduleDefinition(
    job=slack_job,
    cron_schedule="0 */6 * * *"  # Run every 6 hours
)

# Create definitions
defs = Definitions(
    assets=[slack_channel_info, slack_users, scrape_slack_content],
    schedules=[slack_schedule],
    jobs=[slack_job]
) 