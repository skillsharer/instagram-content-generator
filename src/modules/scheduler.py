"""Scheduler and automation module for Instagram Content Generator."""

import time
import threading
import shutil
from typing import Dict, Optional, Set
from datetime import datetime
from pathlib import Path
import signal
import sys

import schedule
from loguru import logger

from .config_manager import config
from .video_scanner import FileScanner
from .content_analyzer import ContentAnalyzer
from .caption_generator import CaptionGenerator
from .instagram_uploader import InstagramUploader
from .monitoring import system_monitor


class ContentProcessor:
    """Processes content files through the complete pipeline."""
    
    def __init__(self):
        """Initialize content processor."""
        self.content_analyzer = ContentAnalyzer()
        self.caption_generator = CaptionGenerator()
        self.instagram_uploaders: Dict[str, InstagramUploader] = {}
        
        # Processing statistics
        self.stats = {
            "total_processed": 0,
            "successful_uploads": 0,
            "failed_uploads": 0,
            "analysis_failures": 0,
            "caption_failures": 0,
        }
    
    def get_or_create_uploader(self, username: str) -> Optional[InstagramUploader]:
        """Get or create Instagram uploader for user.
        
        Args:
            username: Instagram username
            
        Returns:
            InstagramUploader instance or None if failed
        """
        if username not in self.instagram_uploaders:
            try:
                # For now, use global credentials - in production you'd have per-user credentials
                uploader = InstagramUploader(
                    config.settings.instagram_username,
                    config.settings.instagram_password
                )
                
                if uploader.authenticate():
                    self.instagram_uploaders[username] = uploader
                    logger.info(f"Created Instagram uploader for {username}")
                else:
                    logger.error(f"Failed to authenticate Instagram uploader for {username}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error creating uploader for {username}: {str(e)}")
                system_monitor.log_error(f"Uploader creation failed: {str(e)}", "authentication")
                return None
        
        return self.instagram_uploaders.get(username)
    
    def process_file(self, file_info: Dict) -> bool:
        """Process a single file through the complete pipeline.
        
        Args:
            file_info: File information from scanner
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = Path(file_info['file_path'])
            username = file_info.get('username', 'unknown')
            content_type = file_info.get('content_type', 'unknown')
            
            logger.info(f"Processing {content_type} file: {file_path.name} for {username}")
            
            # Step 1: Analyze content
            logger.debug("Analyzing content...")
            analysis_result = self.content_analyzer.analyze_file(file_path)
            
            if "error" in analysis_result:
                logger.error(f"Content analysis failed: {analysis_result['error']}")
                self.stats["analysis_failures"] += 1
                system_monitor.log_error(
                    f"Analysis failed: {analysis_result['error']}", 
                    "content_analysis",
                    {"file_path": str(file_path), "username": username}
                )
                return False
            
            logger.debug(f"Analysis complete. Category: {analysis_result.get('category', 'unknown')}")
            
            # Step 2: Generate caption
            logger.debug("Generating caption...")
            try:
                caption = self.caption_generator.generate_caption(
                    analysis_result,
                    username=username,
                    style="engaging"
                )
            except Exception as e:
                logger.error(f"Caption generation failed: {str(e)}")
                self.stats["caption_failures"] += 1
                system_monitor.log_error(
                    f"Caption generation failed: {str(e)}", 
                    "caption_generation",
                    {"file_path": str(file_path), "username": username}
                )
                return False
            
            logger.debug(f"Caption generated: {len(caption)} characters")
            
            # Step 3: Upload to Instagram
            logger.debug("Uploading to Instagram...")
            uploader = self.get_or_create_uploader(username)
            
            if not uploader:
                logger.error(f"No uploader available for {username}")
                self.stats["failed_uploads"] += 1
                return False
            
            # Prepare extra data
            extra_data = {
                "analysis": analysis_result,
                "processed_time": datetime.now().isoformat(),
                "file_hash": file_info.get('file_hash', ''),
            }
            
            # Upload based on content type
            if content_type == "image":
                upload_result = uploader.upload_photo(file_path, caption, extra_data)
            elif content_type == "video":
                upload_result = uploader.upload_video(file_path, caption, extra_data=extra_data)
            else:
                logger.error(f"Unsupported content type: {content_type}")
                self.stats["failed_uploads"] += 1
                return False
            
            # Check upload result
            if upload_result.get("success"):
                logger.info(f"Successfully uploaded {file_path.name} for {username}")
                self.stats["successful_uploads"] += 1
                self.stats["total_processed"] += 1
                
                # Move file to processed directory
                self._move_to_processed(file_path, username, "success")
                
                # Update monitoring stats
                system_monitor.update_stats(
                    processed_files=1,
                    successful_uploads=1
                )
                
                return True
            else:
                error_msg = upload_result.get("error", "Unknown upload error")
                logger.error(f"Upload failed for {file_path.name}: {error_msg}")
                self.stats["failed_uploads"] += 1
                
                # Move file to failed directory
                self._move_to_processed(file_path, username, "failed", error_msg)
                
                # Update monitoring stats
                system_monitor.update_stats(failed_uploads=1)
                system_monitor.log_error(
                    f"Upload failed: {error_msg}",
                    "instagram_upload",
                    {"file_path": str(file_path), "username": username}
                )
                
                return False
                
        except Exception as e:
            logger.error(f"Error processing file {file_info.get('file_path', 'unknown')}: {str(e)}")
            self.stats["failed_uploads"] += 1
            system_monitor.log_error(
                f"File processing error: {str(e)}",
                "processing_error",
                {"file_info": file_info}
            )
            return False
    
    def _move_to_processed(self, file_path: Path, username: str, status: str, error_msg: str = ""):
        """Move file to processed directory.
        
        Args:
            file_path: Original file path
            username: Username
            status: Processing status ("success" or "failed")
            error_msg: Error message if failed
        """
        try:
            user_paths = config.get_user_paths(username)
            
            if status == "success":
                if "videos" in str(file_path):
                    dest_dir = user_paths["processed_videos"]
                else:
                    dest_dir = user_paths["processed_images"]
            else:
                dest_dir = user_paths["failed"]
            
            # Create destination directory
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Move file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_path = dest_dir / f"{timestamp}_{file_path.name}"
            
            # Use shutil.move to handle cross-device moves (Docker volumes)
            shutil.move(str(file_path), str(dest_path))
            logger.debug(f"Moved {file_path.name} to {dest_path}")
            
            # Create metadata file for failed uploads
            if status == "failed" and error_msg:
                metadata_path = dest_path.with_suffix(dest_path.suffix + ".meta")
                metadata = {
                    "original_path": str(file_path),
                    "processed_time": datetime.now().isoformat(),
                    "status": status,
                    "error": error_msg,
                    "username": username,
                }
                
                with open(metadata_path, 'w') as f:
                    import json
                    json.dump(metadata, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error moving processed file: {str(e)}")
    
    def get_stats(self) -> Dict:
        """Get processing statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.stats.copy()


class InstagramScheduler:
    """Main scheduler for Instagram content automation."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.file_scanner = FileScanner()
        self.content_processor = ContentProcessor()
        self.is_running = False
        self.processing_thread = None
        
        # Track managed users
        self.managed_users: Set[str] = set()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Instagram Scheduler initialized")
    
    def add_user(self, username: str) -> bool:
        """Add user to automation.
        
        Args:
            username: Instagram username
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            if username in self.managed_users:
                logger.info(f"User {username} already being managed")
                return True
            
            # Add user directory scanning
            if self.file_scanner.add_user_directory(username):
                # Perform initial scan
                found_files = self.file_scanner.scan_user_directories(username)
                
                self.managed_users.add(username)
                logger.info(f"Added user {username} to automation. Found {len(found_files)} existing files.")
                
                return True
            else:
                logger.error(f"Failed to add user {username}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding user {username}: {str(e)}")
            return False
    
    def start(self) -> bool:
        """Start the scheduler.
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            if self.is_running:
                logger.warning("Scheduler is already running")
                return True
            
            logger.info("Starting Instagram Content Scheduler")
            
            # Setup scheduled tasks
            self._setup_schedule()
            
            # Start processing thread
            self.is_running = True
            self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
            self.processing_thread.start()
            
            # Start main schedule loop
            self._schedule_loop()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            self.is_running = False
            return False
    
    def stop(self):
        """Stop the scheduler gracefully."""
        try:
            logger.info("Stopping Instagram Content Scheduler")
            
            self.is_running = False
            
            # Stop file watchers
            self.file_scanner.stop_watching()
            
            # Wait for processing thread to finish
            if self.processing_thread and self.processing_thread.is_alive():
                logger.info("Waiting for processing thread to finish...")
                self.processing_thread.join(timeout=30)
            
            # Logout from Instagram
            for uploader in self.content_processor.instagram_uploaders.values():
                uploader.logout()
            
            # Shutdown monitoring
            system_monitor.shutdown()
            
            logger.info("Scheduler stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
    
    def _setup_schedule(self):
        """Setup scheduled tasks."""
        try:
            # Scan for new files periodically
            scan_interval = config.settings.scan_interval_minutes
            schedule.every(scan_interval).minutes.do(self._scheduled_scan)
            logger.info(f"Scheduled directory scanning every {scan_interval} minutes")
            
            # System health checks
            schedule.every(5).minutes.do(self._system_health_check)
            logger.info("Scheduled system health checks every 5 minutes")
            
            # Cleanup old files
            schedule.every().day.at("02:00").do(self._daily_cleanup)
            logger.info("Scheduled daily cleanup at 02:00")
            
            # Statistics reporting
            schedule.every().hour.do(self._hourly_stats)
            logger.info("Scheduled hourly statistics reporting")
            
        except Exception as e:
            logger.error(f"Error setting up schedule: {str(e)}")
    
    def _schedule_loop(self):
        """Main schedule loop."""
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
                
        except Exception as e:
            logger.error(f"Error in schedule loop: {str(e)}")
            self.is_running = False
    
    def _processing_loop(self):
        """Background processing loop for queued files."""
        try:
            while self.is_running:
                # Get next file to process
                next_file = self.file_scanner.get_next_file()
                
                if next_file:
                    # Mark as processing
                    self.file_scanner.mark_processing(next_file['file_hash'])
                    
                    # Process the file
                    success = self.content_processor.process_file(next_file)
                    
                    # Mark as completed
                    self.file_scanner.mark_completed(next_file['file_hash'], success)
                    
                    if not success:
                        # Mark as failed with retry logic
                        self.file_scanner.mark_failed(
                            next_file['file_hash'],
                            "Processing failed",
                            max_attempts=3
                        )
                else:
                    # No files to process, wait a bit
                    time.sleep(10)
                
                # Update queue size in monitoring
                queue_status = self.file_scanner.get_queue_status()
                system_monitor.update_stats(queue_size=queue_status.get("total_queue_size", 0))
                
        except Exception as e:
            logger.error(f"Error in processing loop: {str(e)}")
            system_monitor.log_error(f"Processing loop error: {str(e)}", "processing_loop")
    
    def _scheduled_scan(self):
        """Perform scheduled directory scan."""
        try:
            logger.info("Performing scheduled directory scan")
            
            total_found = 0
            for username in self.managed_users:
                found_files = self.file_scanner.scan_user_directories(username)
                total_found += len(found_files)
                
                if found_files:
                    logger.info(f"Found {len(found_files)} new files for {username}")
            
            if total_found == 0:
                logger.debug("No new files found in scheduled scan")
            
        except Exception as e:
            logger.error(f"Error in scheduled scan: {str(e)}")
            system_monitor.log_error(f"Scheduled scan error: {str(e)}", "scheduled_scan")
    
    def _system_health_check(self):
        """Perform system health check."""
        try:
            # Update system metrics
            system_monitor.update_stats()
            
            # Log health status
            health = system_monitor.get_health_status()
            if health["status"] != "healthy":
                logger.warning(f"System health: {health['status']} - Issues: {health.get('issues', [])}")
            
        except Exception as e:
            logger.error(f"Error in health check: {str(e)}")
    
    def _daily_cleanup(self):
        """Perform daily cleanup tasks."""
        try:
            logger.info("Performing daily cleanup")
            
            # Cleanup old queue entries
            self.file_scanner.cleanup_old_entries(days_to_keep=30)
            
            # Clean up temporary files
            temp_dir = Path("temp")
            if temp_dir.exists():
                for temp_file in temp_dir.glob("*"):
                    if temp_file.is_file():
                        # Remove files older than 1 day
                        if (datetime.now() - datetime.fromtimestamp(temp_file.stat().st_mtime)).days > 1:
                            temp_file.unlink()
                            logger.debug(f"Cleaned up temp file: {temp_file}")
            
            logger.info("Daily cleanup completed")
            
        except Exception as e:
            logger.error(f"Error in daily cleanup: {str(e)}")
    
    def _hourly_stats(self):
        """Log hourly statistics."""
        try:
            # Get processing stats
            process_stats = self.content_processor.get_stats()
            
            # Get queue stats
            queue_stats = self.file_scanner.get_queue_status()
            
            # Get system metrics
            metrics = system_monitor.get_metrics()
            
            logger.info(
                f"Hourly Stats - "
                f"Processed: {process_stats['total_processed']}, "
                f"Success: {process_stats['successful_uploads']}, "
                f"Failed: {process_stats['failed_uploads']}, "
                f"Queue: {queue_stats.get('total_queue_size', 0)}, "
                f"CPU: {metrics.get('system', {}).get('cpu_usage_percent', 0):.1f}%, "
                f"Memory: {metrics.get('system', {}).get('memory_usage_percent', 0):.1f}%"
            )
            
        except Exception as e:
            logger.error(f"Error in hourly stats: {str(e)}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop()
        sys.exit(0)
    
    def get_status(self) -> Dict:
        """Get scheduler status.
        
        Returns:
            Status dictionary
        """
        try:
            return {
                "is_running": self.is_running,
                "managed_users": list(self.managed_users),
                "processing_stats": self.content_processor.get_stats(),
                "queue_stats": self.file_scanner.get_queue_status(),
                "uptime": (datetime.now() - system_monitor.start_time).total_seconds() if system_monitor else 0,
            }
        except Exception as e:
            logger.error(f"Error getting status: {str(e)}")
            return {"error": str(e)}