import sys
import threading
import os
import re
import queue
import time
import atexit
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union

# Global queue for all log messages
_GLOBAL_LOG_QUEUE = queue.Queue()

class LogQueueConsumer(threading.Thread):
    """
    Background thread that consumes log messages from the global queue
    and writes them to the appropriate streams and files.
    """
    def __init__(self, log_queue: queue.Queue):
        super().__init__(name="LogQueueConsumer", daemon=True)
        self.log_queue = log_queue
        self.running = True
        self.file_handles: Dict[Path, Any] = {}
        self.max_thread_name_len = 0
        self.width_lock = threading.Lock()

    def register_names(self, names: List[str]):
        """Synchronously update the max thread name length for alignment."""
        with self.width_lock:
            for name in names:
                self.max_thread_name_len = max(self.max_thread_name_len, len(str(name)))

    def run(self):
        while self.running or not self.log_queue.empty():
            try:
                # Use timeout to allow checking self.running
                record = self.log_queue.get(timeout=0.1)
                
                if record == "STOP":
                    break
                
                # Check for control messages
                if isinstance(record, tuple) and record[0] == "REGISTER_NAMES":
                    self.register_names(record[1])
                    self.log_queue.task_done()
                    continue

                timestamp, level, message, thread_name, stream_type, log_dir = record
                
                with self.width_lock:
                    # Update max seen so far to handle unregistered threads gracefully
                    self.max_thread_name_len = max(self.max_thread_name_len, len(str(thread_name)))
                    display_width = self.max_thread_name_len
                
                # Format: ${time}  ${thread_name}  ${LOG_LEVEL}  ||  ${message}
                padded_name = f"{thread_name:<{display_width}}"
                formatted_msg = f"{timestamp}  {padded_name}  {level:<5}  ||  {message}\n"
                
                # 1. Write to console (serialized)
                if stream_type == "stderr":
                    sys.__stderr__.write(formatted_msg)
                    sys.__stderr__.flush()
                else:
                    sys.__stdout__.write(formatted_msg)
                    sys.__stdout__.flush()
                
                # 2. Write to thread-specific file
                if log_dir:
                    safe_name = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in thread_name])
                    log_file = log_dir / f"{safe_name}.log"
                    
                    if log_file not in self.file_handles:
                        log_dir.mkdir(parents=True, exist_ok=True)
                        self.file_handles[log_file] = open(log_file, "a", encoding="utf-8")
                    
                    f = self.file_handles[log_file]
                    f.write(formatted_msg)
                    f.flush()
                
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # Last resort error reporting
                try:
                    sys.__stderr__.write(f"LOG_CONSUMER_ERROR: {e}\n")
                except:
                    pass

    def stop(self):
        self.running = False
        self.log_queue.put("STOP")
        self.join()
        # Close all file handles
        for f in self.file_handles.values():
            try:
                f.close()
            except:
                pass
        self.file_handles.clear()

# Global consumer instance and its lock
_CONSUMER: Optional[LogQueueConsumer] = None
_CONSUMER_LOCK = threading.Lock()

def _ensure_consumer_running():
    global _CONSUMER
    with _CONSUMER_LOCK:
        if _CONSUMER is None or not _CONSUMER.is_alive():
            _CONSUMER = LogQueueConsumer(_GLOBAL_LOG_QUEUE)
            _CONSUMER.start()
            atexit.register(stop_global_logger)

class LogProxy:
    """
    A stdout/stderr proxy that pushes complete lines to the global log queue.
    Uses threading.local for lock-free per-thread buffering.
    """
    def __init__(self, level: str, stream_type: str, log_dir: Optional[Path]):
        self.level = level
        self.stream_type = stream_type
        self.log_dir = log_dir
        self.local = threading.local()

    def _get_buffer(self) -> str:
        if not hasattr(self.local, 'buffer'):
            self.local.buffer = ""
        return self.local.buffer

    def _set_buffer(self, val: str):
        self.local.buffer = val

    def _sanitize(self, data: str) -> str:
        """Strip control characters like \r and \b that mess up serialized logs."""
        if not data:
            return data
        # Remove carriage return and backspace
        data = data.replace('\r', '').replace('\b', '')
        # Remove ANSI escape sequences if any
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        data = ansi_escape.sub('', data)
        return data

    def write(self, data: str):
        if not data:
            return
            
        data = self._sanitize(data)
        buf = self._get_buffer()
        buf += data
        
        # Extract complete lines
        while '\n' in buf:
            line, rest = buf.split('\n', 1)
            buf = rest
            
            # Put in queue
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            _GLOBAL_LOG_QUEUE.put((
                timestamp,
                self.level,
                line,
                threading.current_thread().name,
                self.stream_type,
                self.log_dir
            ))
        
        self._set_buffer(buf)

    def flush(self):
        pass

    def close(self):
        """Push any remaining partial lines."""
        buf = self._get_buffer()
        if buf:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            _GLOBAL_LOG_QUEUE.put((
                timestamp,
                self.level,
                buf,
                threading.current_thread().name,
                self.stream_type,
                self.log_dir
            ))
            self._set_buffer("")

class ThreadLogger:
    """
    Context manager to enable serialized per-thread logging via a global queue.
    Automatically handles nested or parallel entrants via refcounting.
    """
    _refcount = 0
    _refcount_lock = threading.Lock()
    _original_stdout = None
    _original_stderr = None

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir

    @classmethod
    def create(cls, log_dir: Path, names: Optional[List[str]] = None):
        """
        Factory method to create a ThreadLogger and register expected thread names for alignment.
        """
        _ensure_consumer_running()
        if names and _CONSUMER:
            _CONSUMER.register_names(names)
        return cls(log_dir)

    @staticmethod
    def register_names(names: List[str]):
        """
        Register expected thread names for the global logger.
        """
        _ensure_consumer_running()
        if _CONSUMER:
            _CONSUMER.register_names(names)

    def __enter__(self):
        _ensure_consumer_running()
        
        with ThreadLogger._refcount_lock:
            if ThreadLogger._refcount == 0:
                ThreadLogger._original_stdout = sys.stdout
                ThreadLogger._original_stderr = sys.stderr
                sys.stdout = LogProxy("INFO", "stdout", self.log_dir)
                sys.stderr = LogProxy("ERROR", "stderr", self.log_dir)
            ThreadLogger._refcount += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with ThreadLogger._refcount_lock:
            ThreadLogger._refcount -= 1
            if ThreadLogger._refcount == 0:
                # Flush proxies before restoring
                if isinstance(sys.stdout, LogProxy): sys.stdout.close()
                if isinstance(sys.stderr, LogProxy): sys.stderr.close()
                
                sys.stdout = ThreadLogger._original_stdout
                sys.stderr = ThreadLogger._original_stderr
                ThreadLogger._original_stdout = None
                ThreadLogger._original_stderr = None

def stop_global_logger():
    """Manually stop the background log consumer."""
    global _CONSUMER
    with _CONSUMER_LOCK:
        if _CONSUMER:
            _CONSUMER.stop()
            _CONSUMER = None

def thread_task_wrapper(new_name, func, *args, **kwargs):
    """
    Wraps a function call to set a descriptive thread name during execution.
    """
    def wrapper():
        current_thread = threading.current_thread()
        original_name = current_thread.name
        current_thread.name = new_name
        try:
            return func(*args, **kwargs)
        finally:
            current_thread.name = original_name
    return wrapper
