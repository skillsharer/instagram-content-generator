"""Logging and monitoring module for Instagram Content Generator."""

import json
import sys
import traceback
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import psutil
import platform
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from urllib.parse import urlparse

from loguru import logger

from .config_manager import config


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint."""
    
    def __init__(self, *args, monitor_instance=None, **kwargs):
        self.monitor = monitor_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests for health check."""
        try:
            parsed_path = urlparse(self.path)
            
            if parsed_path.path == '/health':
                self._handle_health_check()
            elif parsed_path.path == '/metrics':
                self._handle_metrics()
            elif parsed_path.path == '/status':
                self._handle_status()
            else:
                self._send_not_found()
                
        except Exception as e:
            logger.error(f"Error in health check handler: {str(e)}")
            self._send_error(500, str(e))
    
    def _handle_health_check(self):
        """Handle basic health check."""
        try:
            health_status = self.monitor.get_health_status() if self.monitor else {"status": "unknown"}
            
            if health_status.get("status") == "healthy":
                self._send_json_response(health_status, 200)
            else:
                self._send_json_response(health_status, 503)
                
        except Exception as e:
            self._send_error(500, f"Health check failed: {str(e)}")
    
    def _handle_metrics(self):
        """Handle metrics endpoint."""
        try:
            metrics = self.monitor.get_metrics() if self.monitor else {}
            self._send_json_response(metrics, 200)
        except Exception as e:
            self._send_error(500, f"Metrics failed: {str(e)}")
    
    def _handle_status(self):
        """Handle detailed status endpoint."""
        try:
            status = self.monitor.get_detailed_status() if self.monitor else {}
            self._send_json_response(status, 200)
        except Exception as e:
            self._send_error(500, f"Status failed: {str(e)}")
    
    def _send_json_response(self, data: Dict, status_code: int = 200):
        """Send JSON response."""
        response = json.dumps(data, indent=2, default=str)
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def _send_not_found(self):
        """Send 404 response."""
        self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Not Found')
    
    def _send_error(self, status_code: int, message: str):
        """Send error response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_response = json.dumps({"error": message})
        self.wfile.write(error_response.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to prevent default logging."""
        pass  # Suppress default HTTP server logs


class SystemMonitor:
    """System monitoring and health checking for Raspberry Pi deployment."""
    
    def __init__(self):
        """Initialize system monitor."""
        self.start_time = datetime.now()
        self.stats = {
            "uptime": 0,
            "processed_files": 0,
            "failed_uploads": 0,
            "successful_uploads": 0,
            "queue_size": 0,
            "last_activity": None,
            "errors_last_hour": 0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
            "temperature": None,
        }
        
        self.health_server = None
        self.health_thread = None
        
        # Error tracking
        self.recent_errors = []
        self.error_counts = {}
        
        # System info
        self.system_info = self._get_system_info()
        
        # Setup health check server if enabled
        if config.settings.health_check_enabled:
            self._start_health_server()
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            return {
                "platform": platform.platform(),
                "architecture": platform.architecture(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "hostname": platform.node(),
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting system info: {str(e)}")
            return {}
    
    def _start_health_server(self):
        """Start health check HTTP server."""
        try:
            def handler_factory(monitor_instance):
                return lambda *args, **kwargs: HealthCheckHandler(*args, monitor_instance=monitor_instance, **kwargs)
            
            self.health_server = HTTPServer(
                ('0.0.0.0', config.settings.health_check_port),
                handler_factory(self)
            )
            
            self.health_thread = threading.Thread(
                target=self.health_server.serve_forever,
                daemon=True
            )
            self.health_thread.start()
            
            logger.info(f"Health check server started on port {config.settings.health_check_port}")
            
        except Exception as e:
            logger.error(f"Failed to start health check server: {str(e)}")
    
    def update_stats(self, **kwargs):
        """Update monitoring statistics.
        
        Args:
            **kwargs: Statistics to update
        """
        try:
            for key, value in kwargs.items():
                if key in self.stats:
                    if key in ['processed_files', 'failed_uploads', 'successful_uploads']:
                        self.stats[key] += value  # Increment counters
                    else:
                        self.stats[key] = value  # Set values
            
            self.stats['last_activity'] = datetime.now().isoformat()
            self.stats['uptime'] = (datetime.now() - self.start_time).total_seconds()
            
            # Update system metrics
            self._update_system_metrics()
            
        except Exception as e:
            logger.error(f"Error updating stats: {str(e)}")
    
    def _update_system_metrics(self):
        """Update system performance metrics."""
        try:
            # CPU usage
            self.stats['cpu_usage'] = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.stats['memory_usage'] = memory.percent
            self.stats['memory_available_mb'] = memory.available // (1024 * 1024)
            
            # Disk usage for the working directory
            disk = psutil.disk_usage('/')
            self.stats['disk_usage'] = (disk.used / disk.total) * 100
            self.stats['disk_free_gb'] = disk.free // (1024 * 1024 * 1024)
            
            # Try to get CPU temperature (Raspberry Pi specific)
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = int(f.read().strip()) / 1000
                    self.stats['temperature'] = temp
            except:
                self.stats['temperature'] = None
                
        except Exception as e:
            logger.error(f"Error updating system metrics: {str(e)}")
    
    def log_error(self, error_message: str, error_type: str = "general", context: Optional[Dict] = None):
        """Log and track errors.
        
        Args:
            error_message: Error message
            error_type: Type of error
            context: Additional context
        """
        try:
            error_entry = {
                "timestamp": datetime.now().isoformat(),
                "message": error_message,
                "type": error_type,
                "context": context or {}
            }
            
            # Add to recent errors (keep last 100)
            self.recent_errors.append(error_entry)
            if len(self.recent_errors) > 100:
                self.recent_errors.pop(0)
            
            # Count error types
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
            
            # Count recent errors for health check
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_count = sum(
                1 for error in self.recent_errors
                if datetime.fromisoformat(error['timestamp']) > one_hour_ago
            )
            self.stats['errors_last_hour'] = recent_count
            
            logger.error(f"[{error_type}] {error_message}", extra=context)
            
        except Exception as e:
            logger.error(f"Error logging error: {str(e)}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get basic health status.
        
        Returns:
            Health status dictionary
        """
        try:
            # Determine health status
            status = "healthy"
            issues = []
            
            # Check CPU usage
            if self.stats['cpu_usage'] > 90:
                status = "unhealthy"
                issues.append("High CPU usage")
            
            # Check memory usage
            if self.stats['memory_usage'] > 90:
                status = "unhealthy"
                issues.append("High memory usage")
            
            # Check disk usage
            if self.stats['disk_usage'] > 95:
                status = "unhealthy"
                issues.append("Low disk space")
            
            # Check temperature (if available)
            if self.stats.get('temperature') and self.stats['temperature'] > 80:
                status = "warning" if status == "healthy" else status
                issues.append("High temperature")
            
            # Check error rate
            if self.stats['errors_last_hour'] > 10:
                status = "warning" if status == "healthy" else status
                issues.append("High error rate")
            
            # Check last activity
            if self.stats.get('last_activity'):
                last_activity = datetime.fromisoformat(self.stats['last_activity'])
                if datetime.now() - last_activity > timedelta(hours=1):
                    status = "warning" if status == "healthy" else status
                    issues.append("No recent activity")
            
            return {
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": self.stats['uptime'],
                "issues": issues,
                "version": "1.0.0",
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {str(e)}")
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics.
        
        Returns:
            Metrics dictionary
        """
        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": self.stats['uptime'],
                "processing": {
                    "processed_files": self.stats['processed_files'],
                    "successful_uploads": self.stats['successful_uploads'],
                    "failed_uploads": self.stats['failed_uploads'],
                    "queue_size": self.stats['queue_size'],
                    "success_rate": (
                        self.stats['successful_uploads'] / 
                        max(1, self.stats['successful_uploads'] + self.stats['failed_uploads'])
                    ) * 100
                },
                "system": {
                    "cpu_usage_percent": self.stats['cpu_usage'],
                    "memory_usage_percent": self.stats['memory_usage'],
                    "memory_available_mb": self.stats.get('memory_available_mb', 0),
                    "disk_usage_percent": self.stats['disk_usage'],
                    "disk_free_gb": self.stats.get('disk_free_gb', 0),
                    "temperature_celsius": self.stats.get('temperature'),
                },
                "errors": {
                    "errors_last_hour": self.stats['errors_last_hour'],
                    "total_error_types": len(self.error_counts),
                    "error_counts": self.error_counts,
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed status including recent errors and system info.
        
        Returns:
            Detailed status dictionary
        """
        try:
            return {
                "health": self.get_health_status(),
                "metrics": self.get_metrics(),
                "system_info": self.system_info,
                "recent_errors": self.recent_errors[-10:],  # Last 10 errors
                "configuration": {
                    "health_check_enabled": config.settings.health_check_enabled,
                    "health_check_port": config.settings.health_check_port,
                    "log_level": config.settings.log_level,
                    "scan_interval_minutes": config.settings.scan_interval_minutes,
                    "upload_delay_minutes": config.settings.upload_delay_minutes,
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed status: {str(e)}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def shutdown(self):
        """Shutdown monitoring services."""
        try:
            if self.health_server:
                self.health_server.shutdown()
                logger.info("Health check server stopped")
                
            if self.health_thread:
                self.health_thread.join(timeout=5)
                
        except Exception as e:
            logger.error(f"Error during monitor shutdown: {str(e)}")


class LoggingManager:
    """Manages application logging configuration."""
    
    def __init__(self):
        """Initialize logging manager."""
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration."""
        try:
            # Remove default logger
            logger.remove()
            
            # Console logging
            logger.add(
                sys.stderr,
                level=config.settings.log_level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                colorize=True
            )
            
            # File logging
            logger.add(
                config.settings.log_file_path,
                level=config.settings.log_level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation="1 day",
                retention="30 days",
                compression="gz",
                serialize=False
            )
            
            # Error-only file
            error_log_path = config.settings.log_file_path.parent / "errors.log"
            logger.add(
                error_log_path,
                level="ERROR",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation="1 week",
                retention="60 days",
                compression="gz"
            )
            
            # JSON structured logging for monitoring
            json_log_path = config.settings.log_file_path.parent / "structured.log"
            logger.add(
                json_log_path,
                level="INFO",
                format="{message}",
                rotation="1 day",
                retention="7 days",
                serialize=True
            )
            
            logger.info("Logging system initialized")
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            # Fallback to basic logging
            logger.add(sys.stderr, level="INFO")


def setup_exception_handler(monitor: SystemMonitor):
    """Setup global exception handler.
    
    Args:
        monitor: SystemMonitor instance
    """
    def exception_handler(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.error(f"Uncaught exception: {error_msg}")
        
        monitor.log_error(
            f"Uncaught {exc_type.__name__}: {str(exc_value)}",
            "uncaught_exception",
            {"traceback": error_msg}
        )
    
    sys.excepthook = exception_handler


# Global instances
logging_manager = LoggingManager()
system_monitor = SystemMonitor()

# Setup exception handling
setup_exception_handler(system_monitor)