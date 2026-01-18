# Cloud Function Cold Start Performance Testing

This utility tests Google Cloud Functions with guaranteed cold starts, comparing performance with and without Lightrun.

## Structure

- `src/` - Source code modules
  - `main.py` - Main entry point
  - `manager.py` - Test orchestration manager
  - `report.py` - Report generation and statistical analysis
  - `deploy.py` - Function deployment tasks
  - `send_request.py` - HTTP request tasks
  - `delete.py` - Function cleanup tasks
  - `wait_for_cold.py` - Cold start detection tasks

- `test/` - Unit tests
  - `test_report.py` - Tests for report generation and statistics
  - `test_format_duration.py` - Tests for duration formatting
  - `test_statistical_tests.py` - Tests for statistical functions

- `test_results/` - Generated reports and visualizations

## Running Tests

Run all unit tests:
```bash
python3 -m pytest test/ -v
```

Run a specific test file:
```bash
python3 -m pytest test/test_report.py -v
```

## Running the Main Utility

Run the cold start performance test:
```bash
python3 -m test_cold_starts.src.main --lightrun-secret YOUR_SECRET --num-functions 100 --wait-minutes 20
```

Or regenerate reports from existing results:
```bash
python3 test_display_results.py
```

## Statistical Analysis

The utility performs comprehensive statistical analysis:

- **T-Test**: Compares means between with/without Lightrun groups
- **Effect Size (Cohen's d)**: Measures practical significance
  - |d| < 0.2: negligible
  - 0.2 ≤ |d| < 0.5: small
  - 0.5 ≤ |d| < 0.8: medium
  - |d| ≥ 0.8: large
- **F-Test**: Compares variances between groups
- **Standard Deviation**: Measures variability

## Requirements

See `requirements.txt` for dependencies.
