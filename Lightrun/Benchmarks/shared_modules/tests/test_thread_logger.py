import unittest
import threading
import sys
import io
import time
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from shared_modules.thread_logger import ThreadLogger, thread_task_wrapper, stop_global_logger

class TestThreadLoggerAlignment(unittest.TestCase):
    def test_alignment_and_formatting(self):
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
                
                # Pre-register names of varying lengths
                long_name = "VeryLongThreadNameForAlignmentTest"
                names = ["Short", long_name]
                
                with ThreadLogger.create(log_dir, names):
                    def task1():
                        print("Message from short")
                    
                    def task2():
                        print("Message from long")
                    
                    t1 = threading.Thread(target=thread_task_wrapper("Short", task1))
                    t2 = threading.Thread(target=thread_task_wrapper(long_name, task2))
                    
                    t1.start()
                    t2.start()
                    t1.join()
                    t2.join()
                    
                    # Give some time for the consumer thread to process
                    time.sleep(0.5)
                
                # Check Console Output
                stdout_val = mock_real_stdout.getvalue()
                lines = stdout_val.splitlines()
                
                # Format: ${time}  ${thread_name}  ${LOG_LEVEL}  ||  ${message}
                # Example: 2026-01-27 18:30:00.123  Short                                 INFO   ||  Message from short
                
                # Regex to extract parts:
                # 1. Timestamp: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}
                # 2. Spacer: \s\s
                # 3. Padded Name:  (match exactly max_len characters)
                # 4. Spacer: \s\s
                # 5. Level: (INFO|ERROR)\s*
                # 6. Spacer: \s\s
                # 7. Separator: \|\|
                # 8. Spacer: \s\s
                # 9. Message: .*
                
                max_len = len(long_name)
                # We use fixed-width capturing for the padded name
                pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s\s(.{" + str(max_len) + r"})\s\s(INFO|ERROR)\s*? \s\s\|\|\s\s(.*)$")
                
                found_short = False
                found_long = False
                
                for line in lines:
                    # Search for our lines specifically
                    if "Message from" not in line:
                        continue
                        
                    match = pattern.match(line)
                    self.assertTrue(match, f"Line did not match expected format: '{line}'")
                    
                    t_name_padded = match.group(2)
                    msg = match.group(4)
                    
                    if "Message from short" in msg:
                        found_short = True
                        self.assertEqual(t_name_padded.rstrip(), "Short")
                        self.assertEqual(len(t_name_padded), max_len)
                    
                    if "Message from long" in msg:
                        found_long = True
                        self.assertEqual(t_name_padded, long_name)
                        self.assertEqual(len(t_name_padded), max_len)

                self.assertTrue(found_short, "Short thread message not found")
                self.assertTrue(found_long, "Long thread message not found")
                        
        finally:
            sys.__stdout__ = original_real_stdout
            sys.__stderr__ = original_real_stderr
            stop_global_logger()

if __name__ == "__main__":
    unittest.main()
