# GCP Cloud Functions - Node.js

Google Cloud Functions examples and test cases.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Deploy a function:
   ```bash
   gcloud functions deploy FUNCTION_NAME \
     --region=europe-west3 \
     --runtime=nodejs20 \
     --source=. \
     --entry-point=handler \
     --trigger-http
   ```

## Structure

```
.
├── functions/          # Individual Cloud Functions
├── shared/            # Shared code/utilities
└── package.json       # Dependencies
```
