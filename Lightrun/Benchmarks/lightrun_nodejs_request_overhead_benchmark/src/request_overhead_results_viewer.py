"""Results viewer for Request Overhead Benchmark."""

import json
import os
from pathlib import Path

class RequestOverheadResultsViewer:
    """Displays results for request overhead benchmark."""
    
    def display(self, results_dir: Path, report_file: str):
        """Display summary of results."""
    def display(self, results_dir: Path, report_file: str):
        """Display summary of results."""
        print(f"\nResults available in: {results_dir}")
        
        report_path = results_dir / report_file
        if report_path.exists():
            print(f"Report: {report_path}")
        else:
            print("Report file not found.")

        # Generate Plot if matplotlib available
        try:
            import matplotlib.pyplot as plt
            import json
            
            # Find results file
            results_files = list(results_dir.glob("*_results.json"))
            if not results_files:
                return
                
            with open(results_files[0], 'r') as f:
                data = json.load(f)
                
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Baseline
            wo_res = data.get('without_lightrun', {}).get('test_results', [])
            baseline_val = 0
            if wo_res:
                 # Extract mean from iterative 0 or fallback
                 # Assuming same extraction logic as report
                 pass 
                 # For simplicity, let's just parse the report or re-extract?
                 # Re-extract logic here is safer.
                 
            # Re-implement simple extraction for plotting
            def get_means(res_data):
                means = {}
                test_results = res_data.get('test_results', [])
                for res in test_results:
                    if res.get('is_iterative'):
                        for iter_res in res.get('iterations', []):
                            iter_num = iter_res.get('iteration')
                            vals = []
                            for req in iter_res.get('_all_request_results', []):
                                if not req.get('error') and 'handlerRunTime' in req:
                                    vals.append(float(req['handlerRunTime']))
                            if vals:
                                if iter_num not in means: means[iter_num] = []
                                means[iter_num].extend(vals)
                
                final_means = {k: sum(v)/len(v) for k, v in means.items()}
                return final_means

            w_means = get_means(data.get('with_lightrun', {}))
            wo_means = get_means(data.get('without_lightrun', {}))
            
            # Baseline line (constant)
            baseline = wo_means.get(0, 0)
            
            x = sorted(w_means.keys())
            y = [w_means[k] for k in x]
            
            ax.plot(x, y, 'ro-', label='With Lightrun')
            ax.axhline(y=baseline, color='b', linestyle='-', label='Without Lightrun (Baseline)')
            
            ax.set_xlabel('Number of Lightrun Actions')
            ax.set_ylabel('Mean Handler Runtime (ns)')
            ax.set_title('Lightrun Agent Performance Overhead')
            ax.legend()
            ax.grid(True)
            
            plot_path = results_dir / 'overhead_plot.png'
            plt.savefig(plot_path)
            print(f"Plot saved to: {plot_path}")
            
        except ImportError:
            print("matplotlib not found, skipping plot generation.")
        except Exception as e:
            print(f"Error generating plot: {e}")
