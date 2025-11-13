"""
GeoOSAM Logger Module
Provides logging functionality for model usage tracking
"""

import sys
import os

# Fix for QGIS environment
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class GeoOSAMLogger:
    """Logger for GeoOSAM plugin activities"""

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize logger

        Args:
            log_dir: Directory to save log files. If None, uses default location.
        """
        # Set log directory
        if log_dir is None:
            self.log_dir = Path.home() / "GeoOSAM_logs"
        else:
            self.log_dir = Path(log_dir)

        self.log_dir.mkdir(exist_ok=True)

        # Create log file path
        self.log_file = self.log_dir / f"geoosam_{datetime.now().strftime('%Y%m%d')}.log"
        self.json_log_file = self.log_dir / f"geoosam_{datetime.now().strftime('%Y%m%d')}.json"

        # Setup logger
        self.logger = logging.getLogger('GeoOSAM')
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers = []

        # File handler for text logs
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("="*60)
        self.logger.info("GeoOSAM Logger Initialized")
        self.logger.info(f"Log directory: {self.log_dir}")
        self.logger.info("="*60)

    def log_model_initialization(self, model_type: str, device: str, model_choice: str,
                                 success: bool, error: Optional[str] = None):
        """
        Log model initialization event

        Args:
            model_type: "local" or "remote"
            device: "cpu", "cuda", or "mps"
            model_choice: Model name (e.g., "SAM2", "SAM2.1_B", "REMOTE")
            success: Whether initialization was successful
            error: Error message if failed
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "model_initialization",
            "model_type": model_type,
            "device": device,
            "model_choice": model_choice,
            "success": success,
            "error": error
        }

        if success:
            self.logger.info(f"✅ Model initialized: {model_type} | {model_choice} | {device}")
        else:
            self.logger.error(f"❌ Model initialization failed: {model_type} | {model_choice} | {error}")

        self._write_json_log(log_data)

    def log_inference(self, mode: str, model_choice: str, image_shape: tuple,
                     prompt_info: Dict[str, Any], output_info: Dict[str, Any],
                     success: bool, duration: float, error: Optional[str] = None):
        """
        Log inference event

        Args:
            mode: "point", "bbox", or "bbox_batch"
            model_choice: Model name
            image_shape: Shape of input image (H, W, C)
            prompt_info: Dict with prompt details (point_coords, box, etc.)
            output_info: Dict with output details (num_masks, scores, etc.)
            success: Whether inference was successful
            duration: Inference duration in seconds
            error: Error message if failed
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "inference",
            "mode": mode,
            "model_choice": model_choice,
            "input": {
                "image_shape": image_shape,
                "prompt": prompt_info
            },
            "output": output_info,
            "success": success,
            "duration": duration,
            "error": error
        }

        if success:
            self.logger.info(
                f"✅ Inference completed: {mode} | {model_choice} | "
                f"{output_info.get('num_masks', 0)} masks | {duration:.2f}s"
            )
        else:
            self.logger.error(f"❌ Inference failed: {mode} | {model_choice} | {error}")

        self._write_json_log(log_data)

    def log_remote_connection(self, server_url: str, success: bool,
                             message: str, duration: Optional[float] = None):
        """
        Log remote server connection attempt

        Args:
            server_url: Remote server URL
            success: Whether connection was successful
            message: Status message
            duration: Connection test duration in seconds
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "remote_connection",
            "server_url": server_url,
            "success": success,
            "message": message,
            "duration": duration
        }

        if success:
            self.logger.info(f"✅ Remote connection successful: {server_url}")
        else:
            self.logger.warning(f"⚠️ Remote connection failed: {server_url} | {message}")

        self._write_json_log(log_data)

    def log_export(self, class_name: str, feature_count: int, output_path: str, success: bool):
        """
        Log shapefile export event

        Args:
            class_name: Class name being exported
            feature_count: Number of features exported
            output_path: Output file path
            success: Whether export was successful
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "export",
            "class_name": class_name,
            "feature_count": feature_count,
            "output_path": output_path,
            "success": success
        }

        if success:
            self.logger.info(f"✅ Export completed: {class_name} | {feature_count} features | {output_path}")
        else:
            self.logger.error(f"❌ Export failed: {class_name}")

        self._write_json_log(log_data)

    def log_error(self, context: str, error_type: str, error_message: str, traceback: Optional[str] = None):
        """
        Log error event

        Args:
            context: Where the error occurred (e.g., "model_initialization", "inference")
            error_type: Type of error (e.g., "ConnectionError", "ValueError")
            error_message: Error message
            traceback: Full traceback string
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event": "error",
            "context": context,
            "error_type": error_type,
            "error_message": error_message,
            "traceback": traceback
        }

        self.logger.error(f"❌ Error in {context}: {error_type} - {error_message}")
        if traceback:
            self.logger.debug(f"Traceback:\n{traceback}")

        self._write_json_log(log_data)

    def log_info(self, message: str):
        """Log general information"""
        self.logger.info(message)

    def log_warning(self, message: str):
        """Log warning"""
        self.logger.warning(message)

    def log_debug(self, message: str):
        """Log debug information"""
        self.logger.debug(message)

    def _write_json_log(self, log_data: Dict[str, Any]):
        """
        Write log data to JSON file

        Args:
            log_data: Dictionary with log data
        """
        try:
            with open(self.json_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_data, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write JSON log: {e}")

    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get statistics from today's logs

        Returns:
            Dictionary with log statistics
        """
        stats = {
            "total_inferences": 0,
            "successful_inferences": 0,
            "failed_inferences": 0,
            "total_duration": 0.0,
            "models_used": {},
            "modes_used": {},
            "errors": []
        }

        try:
            if not self.json_log_file.exists():
                return stats

            with open(self.json_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line)

                        if log_entry.get('event') == 'inference':
                            stats['total_inferences'] += 1

                            if log_entry.get('success'):
                                stats['successful_inferences'] += 1
                                stats['total_duration'] += log_entry.get('duration', 0)
                            else:
                                stats['failed_inferences'] += 1

                            # Count by model
                            model = log_entry.get('model_choice', 'unknown')
                            stats['models_used'][model] = stats['models_used'].get(model, 0) + 1

                            # Count by mode
                            mode = log_entry.get('mode', 'unknown')
                            stats['modes_used'][mode] = stats['modes_used'].get(mode, 0) + 1

                        elif log_entry.get('event') == 'error':
                            stats['errors'].append({
                                'timestamp': log_entry.get('timestamp'),
                                'context': log_entry.get('context'),
                                'error_type': log_entry.get('error_type'),
                                'message': log_entry.get('error_message')
                            })

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            self.logger.error(f"Failed to read log stats: {e}")

        return stats

    def clear_old_logs(self, days: int = 7):
        """
        Clear log files older than specified days

        Args:
            days: Number of days to keep logs
        """
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

            for log_file in self.log_dir.glob("geoosam_*.log"):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    self.logger.info(f"Deleted old log file: {log_file.name}")

            for json_file in self.log_dir.glob("geoosam_*.json"):
                if json_file.stat().st_mtime < cutoff_date:
                    json_file.unlink()
                    self.logger.info(f"Deleted old JSON log: {json_file.name}")

        except Exception as e:
            self.logger.error(f"Failed to clear old logs: {e}")


# Global logger instance
_logger_instance = None


def get_logger(log_dir: Optional[Path] = None) -> GeoOSAMLogger:
    """
    Get or create global logger instance

    Args:
        log_dir: Directory to save log files

    Returns:
        GeoOSAMLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = GeoOSAMLogger(log_dir)
    return _logger_instance
