# Google Drive API Credentials

This directory should contain your Google Drive API credentials file (`credentials.json`).

## How to Create Service Account Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Navigate to "APIs & Services" > "Credentials".
4. Click "Create Credentials" > "Service Account".
5. Provide a name for the service account and click "Create".
6. Assign the role "Project" > "Viewer" to the service account.
7. Click "Done".
8. Find the service account in the list and click on it.
9. Go to the "Keys" tab and click "Add Key" > "Create new key".
10. Choose "JSON" as the key type and click "Create".
11. The JSON file will be downloaded to your computer.
12. Rename the downloaded file to `credentials.json` and place it in this directory.

## Sharing Google Drive Folders

For the service account to access files in your Google Drive:

1. Get the service account email from the credentials JSON file (look for `client_email`).
2. Share your Google Drive folders with this email address, giving it "Viewer" access.
3. Note the folder IDs (from the URL of your Google Drive folders) and add them to your configuration. 