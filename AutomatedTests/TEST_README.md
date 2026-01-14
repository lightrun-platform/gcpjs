# GCP Cloud Functions Test Suite

This script tests GCP Cloud Functions (Gen1 and Gen2) across Node.js versions 18-24 with Lightrun integration.

## Prerequisites

1. **Python 3.8+** with `requests` library:
   ```bash
   pip install -r requirements.txt
   ```

2. **gcloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project <your-project-id>
   ```

3. **Environment Variables** (required):
   ```bash
   export LIGHTRUN_SECRET="your-lightrun-secret"  # Required - used for agent initialization
   ```
   
   **Username for function naming** (one of the following is required):
   ```bash
   export TEST_USERNAME="your-username"  # Optional - takes precedence over git config
   ```
   OR configure git:
   ```bash
   git config --global user.name "Your Name"
   ```
   The script will use `TEST_USERNAME` environment variable if set, otherwise falls back to git config.
   If neither is available, the script will fail with an error.
   
   **Note**: Uses `TEST_USERNAME` instead of `USERNAME` to avoid conflicts with the system `USERNAME` 
   variable (which is automatically set to your login name on Unix systems).
   
   **Optional environment variables**:
   ```bash
   export GCP_PROJECT="your-gcp-project-id"  # Optional, defaults to "lightrun-temp"
   export GCP_REGION="europe-west1"  # Optional, uses precedence list if not set
   export LIGHTRUN_API_URL="https://api.lightrun.com"  # Optional, defaults to https://api.lightrun.com
   export LIGHTRUN_API_KEY="your-api-key"  # Optional - required for Lightrun API feature tests
   export LIGHTRUN_COMPANY_ID="your-company-id"  # Optional - required for Lightrun API feature tests
   ```
   
   **Note**: All Lightrun configuration values are read from environment variables. 
   The code will validate that `LIGHTRUN_SECRET` and username are set before running tests.

## Usage

```bash
python3 src/test_gcp_functions.py
```

Or make it executable and run directly:
```bash
chmod +x src/test_gcp_functions.py
./src/test_gcp_functions.py
```

## What It Tests

For each combination of:
- **Function Generation**: Gen1 and Gen2
- **Node.js Version**: 18, 19, 20, 21, 22, 23, 24

The script will:

1. **Deploy** the function to GCP
2. **Performance Tests**:
   - Cold start performance (100 requests with 5s delay between each)
   - Warm start performance (100 rapid requests)
   - Average response times
3. **Log Analysis**: Check Cloud Function logs for errors
4. **Lightrun Integration Tests** (if API credentials provided):
   - Snapshot functionality
   - Counter functionality
   - Metric functionality

## Output

- **Console**: Real-time progress and results
- **JSON Files**: Individual results saved to `test-results/<function-name>.json`
- **Summary**: Final summary with statistics

## Test Results Structure

Each result file contains:
```json
{
  "function_name": "test-node20-gen2",
  "gen_version": 2,
  "nodejs_version": 20,
  "deployment_success": true,
  "cold_start_avg_ms": 1234.56,
  "warm_start_avg_ms": 45.67,
  "cold_start_requests": 100,
  "warm_start_requests": 100,
  "logs_error_check": true,
  "snapshot_test": true,
  "counter_test": true,
  "metric_test": true,
  "function_url": "https://...",
  "cleanup_success": true,
  "timestamp": "2026-01-13T10:00:00"
}
```

## Parallel Execution

Tests run in parallel with a concurrency limit of 4 functions at a time to avoid overwhelming GCP APIs.

## Cleanup

All deployed functions are automatically cleaned up after testing, even if tests fail.

## Notes

- The script creates temporary function directories in `test-functions/` which are cleaned up automatically
- Results are saved to `test-results/` directory
- If a function deployment fails, it will be cleaned up and other tests will continue
- Lightrun feature tests require valid API credentials and will be skipped if not provided
