# Test Suite Structure

This test suite has been refactored into a modular structure with clear separation of concerns.

## File Organization

### Core Modules

- **`config.py`** - Configuration settings (regions, API keys, test parameters)
- **`models.py`** - Data models (`TestResult` dataclass)
- **`utils.py`** - Utility functions (command execution)

### Functional Classes

- **`gcp_deployer.py`** - `GCPDeployer` class
  - Handles GCP Cloud Functions deployment
  - Region fallback logic
  - Function deletion
  - Log checking

- **`function_creator.py`** - `FunctionCreator` class
  - Creates test function code
  - Generates `package.json` files
  - Manages temporary function directories

- **`performance_tester.py`** - `PerformanceTester` class
  - Function invocation
  - Cold start testing
  - Warm start testing
  - Performance metrics collection

- **`lightrun_tester.py`** - `LightrunTester` class
  - Agent ID retrieval
  - Snapshot testing
  - Counter testing
  - Metric testing

- **`result_handler.py`** - `ResultHandler` class
  - Result saving to JSON files
  - Summary generation
  - Report formatting

### Orchestration

- **`function_tester.py`** - `FunctionTester` class
  - Orchestrates all testing components
  - Manages test lifecycle
  - Coordinates cleanup

### Entry Point

- **`src/test_gcp_functions.py`** - Main script
  - Entry point for running tests
  - Parallel test execution
  - Exception handling
  - Summary display

## Usage

Run the test suite:

```bash
python3 src/test_gcp_functions.py
```

Or make it executable and run directly:

```bash
chmod +x src/test_gcp_functions.py
./src/test_gcp_functions.py
```

## Benefits of This Structure

1. **Modularity**: Each class has a single responsibility
2. **Testability**: Classes can be tested independently
3. **Maintainability**: Changes to one component don't affect others
4. **Reusability**: Classes can be reused in other scripts
5. **Readability**: Clear separation makes code easier to understand

## Class Responsibilities

- **GCPDeployer**: All GCP API interactions
- **FunctionCreator**: Code generation
- **PerformanceTester**: Performance measurement
- **LightrunTester**: Lightrun API interactions
- **ResultHandler**: Result persistence and reporting
- **FunctionTester**: Test orchestration
