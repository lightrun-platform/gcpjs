import unittest
import threading
import sys
import io
import time
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from shared_modules.thread_logger import ThreadLogger, thread_task_wrapper, stop_global_logger

class TestThreadLoggerSanitization(unittest.TestCase):
    def test_sanitization_of_control_chars(self):
        # Monkeypatch real streams
        original_real_stdout = sys.__stdout__
        original_real_stderr = sys.__stderr__
        
        mock_real_stdout = io.StringIO()
        mock_real_stderr = io.StringIO()
        
        sys.__stdout__ = mock_real_stdout
        sys.__stderr__ = mock_real_stderr
        
        try:
            with TemporaryDirectory() as tmp_dir:
                log_dir = Path(tmp_dir)
                
                with ThreadLogger.create(log_dir, ["TestThread"]):
                    # Write message with \r and ANSI escapes
                    print("Normal part \r Overwrite attempt \x1B[31mRed text\x1B[0m")
                    
                    time.sleep(0.5)
                
                # Check Console Output
                stdout_val = mock_real_stdout.getvalue()
                
                # The output should NOT contain \r or ANSI escapes
                self.assertNotIn("\r", stdout_val)
                self.assertNotIn("\x1B[31m", stdout_val)
                self.assertNotIn("\x1B[0m", stdout_val)
                
                # It should contain the sanitized message
                # "Normal part " + " Overwrite attempt " + "Red text"
                self.assertIn("Normal part  Overwrite attempt Red text", stdout_val)
                
        finally:
            sys.__stdout__ = original_real_stdout
            sys.__stderr__ = original_real_stderr
            stop_global_logger()

if __name__ == "__main__":
    unittest.main()
