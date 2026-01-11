# Lightrun Adapted GCP Cloud Functions Examples

This directory contains Cloud Functions examples adapted for Lightrun integration.

## Structure

```
LightrunAdapted/
├── cloudbuild.yaml          # Cloud Build configuration (supports multiple functions)
├── nodejs-docs-samples/
│   └── functions/
│       └── imagemagick/     # Image processing example
│           ├── index.js
│           ├── package.json
│           └── ...
└── README.md               # This file
```

## Deploying Functions

### Option 1: Using Cloud Build Trigger (Recommended)

1. **Set up Cloud Build Trigger** in GCP Console:
   - Connect repository: `lightrun-platform/gcpjs`
   - Configuration: `Cloud Build configuration file (yaml or json)`
   - Location: `LightrunAdapted/cloudbuild.yaml`

2. **Override Substitution Variables** (NO COMMIT NEEDED):
   - Go to: Cloud Build > Triggers > Edit Trigger > **Substitution variables**
   - Add/override any variable to deploy different functions
   - Changes take effect immediately without committing to repo

3. **Substitution Variables** (all can be overridden):
   - `_FUNCTION_NAME`: Name of the Cloud Function
   - `_RUNTIME`: Node.js runtime (e.g., `nodejs20`)
   - `_REGION`: GCP region (e.g., `europe-west3`)
   - `_FUNCTION_DIR`: Path to function directory in repo
   - `_ENTRY_POINT`: Function entry point name
   - `_TRIGGER_BUCKET`: Storage bucket for triggers
   - `_ENV_VARS`: Environment variables (key=value format, comma-separated)

**Example**: To deploy a different function, just override in trigger settings:
- `_FUNCTION_DIR`: `LightrunAdapted/nodejs-docs-samples/functions/your-example`
- `_ENTRY_POINT`: `yourFunctionName`
- `_TRIGGER_BUCKET`: `your-bucket-name`

### Option 2: Manual Deployment via gcloud

```bash
gcloud functions deploy nadav-gcpjs \
  --gen2 \
  --runtime=nodejs20 \
  --region=europe-west3 \
  --source=LightrunAdapted/nodejs-docs-samples/functions/imagemagick \
  --entry-point=blurOffensiveImages \
  --trigger-bucket=lightrun-image-input \
  --set-env-vars BLURRED_BUCKET_NAME=lightrun-image-output
```

## Adding New Examples

1. **Add your function** to `LightrunAdapted/nodejs-docs-samples/functions/your-example/`

2. **Commit and push** the new function code to the repository

3. **Deploy without code changes**: Override substitution variables in Cloud Build Trigger:
   - `_FUNCTION_DIR`: `LightrunAdapted/nodejs-docs-samples/functions/your-example`
   - `_ENTRY_POINT`: Your function name
   - `_FUNCTION_NAME`: Function name (can reuse existing or create new)
   - `_TRIGGER_BUCKET`: Your trigger bucket
   - `_ENV_VARS`: Your environment variables (comma-separated)

4. **Run the trigger** - no need to commit cloudbuild.yaml changes!

## Current Examples

### imagemagick
- **Path**: `LightrunAdapted/nodejs-docs-samples/functions/imagemagick`
- **Entry Point**: `blurOffensiveImages`
- **Trigger**: Storage bucket (`lightrun-image-input`)
- **Description**: Blurs inappropriate images using Vision API and ImageMagick

## Notes

- All functions use Node.js 20 runtime
- Functions are deployed to `europe-west3` region
- Cloud Build automatically installs dependencies from `package.json`
- No manual build steps needed for Node.js functions
- **You can switch between functions by overriding substitution variables in the Cloud Build trigger - no commits needed!**
