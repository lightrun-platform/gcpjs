"""Results viewer for Request Overhead Benchmark."""

import json
import os
from pathlib import Path

class RequestOverheadResultsViewer:
    """Displays results for request overhead benchmark."""
    
    def display(self, results_dir: Path, report_file: str):
        """Display summary of results."""
        print(f"\nResults available in: {results_dir}")
        
        report_path = results_dir / report_file
        if report_path.exists():
            print(f"Report: {report_path}")
            # We already presumably printed the report content during generation, so maybe just point to it.
        else:
            print("Report file not found.")
