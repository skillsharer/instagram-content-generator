"""Main entry point for Instagram Content Generator."""

import sys
import argparse
from pathlib import Path
from typing import List
from loguru import logger
from .modules.config_manager import config
from .modules.scheduler import InstagramScheduler
from .modules.monitoring import system_monitor


def validate_environment() -> bool:
    """Validate that all required environment variables are set.
    
    Returns:
        True if environment is valid, False otherwise
    """
    try:
        # Check Instagram credentials
        if not config.validate_instagram_credentials():
            logger.error("Instagram credentials not provided. Please set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD")
            return False
        
        # Check OpenAI credentials
        if not config.validate_openai_credentials():
            logger.error("OpenAI API key not provided. Please set OPENAI_API_KEY")
            return False
        
        # Check required directories
        required_dirs = [
            config.settings.shared_folder_path,
            config.settings.processed_folder_path,
            config.settings.log_file_path.parent,
        ]
        
        for directory in required_dirs:
            if not directory.exists():
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {directory}")
                except Exception as e:
                    logger.error(f"Cannot create required directory {directory}: {str(e)}")
                    return False
        
        logger.info("Environment validation successful")
        return True
        
    except Exception as e:
        logger.error(f"Error validating environment: {str(e)}")
        return False


def setup_users(usernames: List[str], scheduler: InstagramScheduler) -> bool:
    """Setup users for automation.
    
    Args:
        usernames: List of Instagram usernames
        scheduler: Scheduler instance
        
    Returns:
        True if all users added successfully, False otherwise
    """
    try:
        success_count = 0
        
        for username in usernames:
            logger.info(f"Setting up user: {username}")
            
            if scheduler.add_user(username):
                success_count += 1
                logger.info(f"Successfully added user: {username}")
            else:
                logger.error(f"Failed to add user: {username}")
        
        if success_count == len(usernames):
            logger.info(f"Successfully setup all {success_count} users")
            return True
        else:
            logger.warning(f"Only {success_count}/{len(usernames)} users setup successfully")
            return success_count > 0  # Continue if at least one user is setup
            
    except Exception as e:
        logger.error(f"Error setting up users: {str(e)}")
        return False


def run_scheduler(usernames: List[str]) -> int:
    """Run the main scheduler.
    
    Args:
        usernames: List of Instagram usernames to manage
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        logger.info("Starting Instagram Content Generator")
        
        # Validate environment
        if not validate_environment():
            logger.error("Environment validation failed")
            return 1
        
        # Create scheduler
        scheduler = InstagramScheduler()
        
        # Setup users
        if not setup_users(usernames, scheduler):
            logger.error("Failed to setup users")
            return 1
        
        # Start scheduler
        logger.info("Starting automation scheduler...")
        if scheduler.start():
            logger.info("Scheduler started successfully")
            return 0
        else:
            logger.error("Failed to start scheduler")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        system_monitor.log_error(f"Main error: {str(e)}", "main_error")
        return 1


def run_single_scan(usernames: List[str]) -> int:
    """Run a single scan without continuous monitoring.
    
    Args:
        usernames: List of Instagram usernames to scan
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        logger.info("Running single scan mode")
        
        # Validate environment
        if not validate_environment():
            logger.error("Environment validation failed")
            return 1
        
        # Import modules for single scan
        try:
            from .modules.video_scanner import FileScanner
            from .modules.content_analyzer import ContentAnalyzer
            from .modules.caption_generator import CaptionGenerator
            from .modules.instagram_uploader import InstagramUploader
        except ImportError:
            # Handle direct execution
            from modules.video_scanner import FileScanner
            from modules.content_analyzer import ContentAnalyzer
            from modules.caption_generator import CaptionGenerator
            from modules.instagram_uploader import InstagramUploader
        
        # Initialize components
        scanner = FileScanner()
        analyzer = ContentAnalyzer()
        caption_gen = CaptionGenerator()
        
        total_processed = 0
        total_success = 0
        
        for username in usernames:
            logger.info(f"Scanning for user: {username}")
            
            # Add user and scan
            scanner.add_user_directory(username)
            found_files = scanner.scan_user_directories(username)
            
            if not found_files:
                logger.info(f"No files found for {username}")
                continue
            
            logger.info(f"Found {len(found_files)} files for {username}")
            
            # Create uploader
            uploader = InstagramUploader(
                config.settings.instagram_username,
                config.settings.instagram_password
            )
            
            if not uploader.authenticate():
                logger.error(f"Failed to authenticate for {username}")
                continue
            
            # Process each file
            while True:
                next_file = scanner.get_next_file()
                if not next_file:
                    break
                
                file_path = Path(next_file['file_path'])
                content_type = next_file.get('content_type', 'unknown')
                
                logger.info(f"Processing: {file_path.name}")
                
                # Analyze content
                analysis = analyzer.analyze_file(file_path)
                if "error" in analysis:
                    logger.error(f"Analysis failed: {analysis['error']}")
                    scanner.mark_failed(next_file['file_hash'], analysis['error'])
                    continue
                
                # Generate caption
                caption = caption_gen.generate_caption(analysis, username)
                
                # Upload
                if content_type == "image":
                    result = uploader.upload_photo(file_path, caption)
                elif content_type == "video":
                    result = uploader.upload_video(file_path, caption)
                else:
                    logger.error(f"Unsupported type: {content_type}")
                    scanner.mark_failed(next_file['file_hash'], f"Unsupported type: {content_type}")
                    continue
                
                total_processed += 1
                
                if result.get("success"):
                    logger.info(f"Successfully uploaded: {file_path.name}")
                    scanner.mark_completed(next_file['file_hash'], True)
                    total_success += 1
                else:
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Upload failed: {error_msg}")
                    scanner.mark_failed(next_file['file_hash'], error_msg)
            
            uploader.logout()
        
        logger.info(f"Single scan complete. Processed: {total_processed}, Success: {total_success}")
        return 0
        
    except Exception as e:
        logger.error(f"Error in single scan: {str(e)}")
        return 1


def show_status() -> int:
    """Show current system status.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Try to get status from running instance via health check
        import requests
        
        health_url = f"http://localhost:{config.settings.health_check_port}/status"
        
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                status = response.json()
                
                print("=== Instagram Content Generator Status ===")
                print(f"Health: {status.get('health', {}).get('status', 'unknown')}")
                print(f"Uptime: {status.get('health', {}).get('uptime_seconds', 0):.0f} seconds")
                
                metrics = status.get('metrics', {})
                processing = metrics.get('processing', {})
                system = metrics.get('system', {})
                
                print(f"\nProcessing:")
                print(f"  Processed Files: {processing.get('processed_files', 0)}")
                print(f"  Successful Uploads: {processing.get('successful_uploads', 0)}")
                print(f"  Failed Uploads: {processing.get('failed_uploads', 0)}")
                print(f"  Success Rate: {processing.get('success_rate', 0):.1f}%")
                print(f"  Queue Size: {processing.get('queue_size', 0)}")
                
                print(f"\nSystem:")
                print(f"  CPU Usage: {system.get('cpu_usage_percent', 0):.1f}%")
                print(f"  Memory Usage: {system.get('memory_usage_percent', 0):.1f}%")
                print(f"  Disk Usage: {system.get('disk_usage_percent', 0):.1f}%")
                
                temp = system.get('temperature_celsius')
                if temp:
                    print(f"  Temperature: {temp:.1f}°C")
                
                errors = metrics.get('errors', {})
                print(f"\nErrors:")
                print(f"  Errors Last Hour: {errors.get('errors_last_hour', 0)}")
                
                return 0
            else:
                print(f"Health check returned status {response.status_code}")
                return 1
                
        except requests.exceptions.RequestException:
            print("No running instance found (health check unavailable)")
            return 1
            
    except Exception as e:
        logger.error(f"Error showing status: {str(e)}")
        return 1


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Instagram Content Generator - Automated content analysis and posting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run continuous monitoring for multiple users
  python -m instagram_content_generator.main run user1 user2 user3
  
  # Run single scan without continuous monitoring
  python -m instagram_content_generator.main scan user1
  
  # Show system status
  python -m instagram_content_generator.main status
  
  # Show help
  python -m instagram_content_generator.main --help

Environment Variables Required:
  INSTAGRAM_USERNAME - Instagram username for posting
  INSTAGRAM_PASSWORD - Instagram password
  OPENAI_API_KEY - OpenAI API key for caption generation
  
Optional Environment Variables:
  SHARED_FOLDER_PATH - Path to shared content folder (default: /shared)
  PROCESSED_FOLDER_PATH - Path to processed files (default: /processed)
  LOG_LEVEL - Logging level (default: INFO)
  SCAN_INTERVAL_MINUTES - Scan interval (default: 30)
  UPLOAD_DELAY_MINUTES - Delay between uploads (default: 60)
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run continuous monitoring and posting')
    run_parser.add_argument(
        'usernames', 
        nargs='+', 
        help='Instagram usernames to manage (corresponds to folder names in shared directory)'
    )
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Run single scan without continuous monitoring')
    scan_parser.add_argument(
        'usernames', 
        nargs='+', 
        help='Instagram usernames to scan'
    )
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    try:
        if args.command == 'run':
            return run_scheduler(args.usernames)
        elif args.command == 'scan':
            return run_single_scan(args.usernames)
        elif args.command == 'status':
            return show_status()
        else:
            parser.print_help()
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())