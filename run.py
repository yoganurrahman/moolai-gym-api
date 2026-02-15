import uvicorn
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

if __name__ == "__main__":
    # Create logs directory if not exists
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Generate log filename with datetime
    log_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"gym_log_{log_datetime}.log"
    log_path = os.path.join(logs_dir, log_filename)

    # Redirect stdout and stderr to log file (while keeping console output)
    class TeeOutput:
        """Write to both console and file simultaneously"""
        def __init__(self, file_path, stream):
            self.file = open(file_path, "a", encoding="utf-8", buffering=1)  # line buffered
            self.stream = stream

        def write(self, data):
            self.stream.write(data)
            self.stream.flush()
            self.file.write(data)
            self.file.flush()

        def flush(self):
            self.stream.flush()
            self.file.flush()

    # Replace stdout and stderr with TeeOutput
    sys.stdout = TeeOutput(log_path, sys.__stdout__)
    sys.stderr = TeeOutput(log_path, sys.__stderr__)

    print(f"=" * 60)
    print(f"Moolai Gym API Starting...")
    print(f"Log file: {log_path}")
    print(f"=" * 60)

    # Uvicorn log config - output to both console and file
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s - %(levelprefix)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": False,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(asctime)s - %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": False,
            },
            "file_format": {
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.FileHandler",
                "formatter": "file_format",
                "filename": log_path,
                "encoding": "utf-8",
            },
            "access": {
                "class": "logging.StreamHandler",
                "formatter": "access",
                "stream": "ext://sys.stdout",
            },
            "access_file": {
                "class": "logging.FileHandler",
                "formatter": "file_format",
                "filename": log_path,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access", "access_file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        workers=1,
        log_config=log_config,
        access_log=True,
    )
