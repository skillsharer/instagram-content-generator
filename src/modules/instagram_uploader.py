"""Instagram uploader module for Instagram Content Generator."""

import time
from pathlib import Path
from typing import Dict, Optional, Union
from datetime import datetime, timedelta

from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, 
    BadPassword, 
    ChallengeRequired,
    FeedbackRequired,
    PleaseWaitFewMinutes
)
from loguru import logger
from PIL import Image
import moviepy.editor as mp

from .config_manager import config


class InstagramUploader:
    """Handles Instagram authentication and content uploading."""
    
    def __init__(self, username: str, password: str):
        """Initialize Instagram uploader.
        
        Args:
            username: Instagram username
            password: Instagram password
        """
        self.username = username
        self.password = password
        self.client = Client()
        self.session_file = Path(f"session_{username}.json")
        self.last_upload_time = None
        self.upload_delay = timedelta(minutes=config.settings.upload_delay_minutes)
        
        # Rate limiting tracking
        self.daily_uploads = 0
        self.last_reset_date = datetime.now().date()
        self.max_daily_uploads = 50  # Conservative limit
        
        # Setup client settings
        self.client.delay_range = [5, 15]  # Random delay between requests
        
    def authenticate(self) -> bool:
        """Authenticate with Instagram.
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Try to load existing session
            if self._load_session():
                logger.info(f"Loaded existing session for {self.username}")
                return True
            
            # Fresh login
            logger.info(f"Performing fresh login for {self.username}")
            
            # Set user agent and device settings for better success rate
            self.client.set_user_agent("Instagram 219.0.0.12.117")
            
            success = self.client.login(self.username, self.password)
            
            if success:
                self._save_session()
                logger.info(f"Successfully authenticated {self.username}")
                return True
            else:
                logger.error(f"Failed to authenticate {self.username}")
                return False
                
        except ChallengeRequired as e:
            logger.warning(f"Challenge required for {self.username}: {str(e)}")
            # In production, you might want to handle challenges automatically
            return False
            
        except BadPassword:
            logger.error(f"Bad password for {self.username}")
            return False
            
        except PleaseWaitFewMinutes:
            logger.warning(f"Rate limited, need to wait for {self.username}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {str(e)}")
            return False
    
    def upload_photo(
        self, 
        image_path: Path, 
        caption: str,
        extra_data: Optional[Dict] = None
    ) -> Dict[str, Union[bool, str]]:
        """Upload a photo to Instagram.
        
        Args:
            image_path: Path to the image file
            caption: Caption for the post
            extra_data: Additional data about the upload
            
        Returns:
            Dictionary with upload result
        """
        try:
            # Check rate limits
            if not self._check_rate_limits():
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "retry_after": self._get_retry_time()
                }
            
            # Wait if needed to avoid rate limiting
            if self.last_upload_time:
                time_since_last = datetime.now() - self.last_upload_time
                if time_since_last < self.upload_delay:
                    wait_time = (self.upload_delay - time_since_last).total_seconds()
                    logger.info(f"Waiting {wait_time:.0f} seconds before upload")
                    time.sleep(wait_time)
            
            # Prepare image
            processed_image_path = self._prepare_image(image_path)
            
            if not processed_image_path:
                return {
                    "success": False,
                    "error": "Failed to prepare image",
                    "file_path": str(image_path)
                }
            
            # Upload the photo
            logger.info(f"Uploading photo: {image_path.name}")
            
            media = self.client.photo_upload(
                processed_image_path,
                caption,
                extra_data=extra_data or {}
            )
            
            # Update tracking
            self.last_upload_time = datetime.now()
            self.daily_uploads += 1
            
            # Clean up processed file if it's different from original
            if processed_image_path != image_path:
                processed_image_path.unlink(missing_ok=True)
            
            logger.info(f"Successfully uploaded photo: {media.pk}")
            
            return {
                "success": True,
                "media_id": media.pk,
                "media_code": media.code,
                "file_path": str(image_path),
                "upload_time": self.last_upload_time.isoformat()
            }
            
        except FeedbackRequired as e:
            logger.error(f"Feedback required (possible content violation): {str(e)}")
            return {
                "success": False,
                "error": "Content feedback required",
                "details": str(e),
                "file_path": str(image_path)
            }
            
        except PleaseWaitFewMinutes:
            logger.warning("Rate limited during upload")
            return {
                "success": False,
                "error": "Rate limited",
                "retry_after": 15 * 60,  # 15 minutes
                "file_path": str(image_path)
            }
            
        except Exception as e:
            logger.error(f"Error uploading photo {image_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": str(image_path)
            }
    
    def upload_video(
        self, 
        video_path: Path, 
        caption: str,
        thumbnail_path: Optional[Path] = None,
        extra_data: Optional[Dict] = None
    ) -> Dict[str, Union[bool, str]]:
        """Upload a video to Instagram.
        
        Args:
            video_path: Path to the video file
            caption: Caption for the post
            thumbnail_path: Optional custom thumbnail
            extra_data: Additional data about the upload
            
        Returns:
            Dictionary with upload result
        """
        try:
            # Check rate limits
            if not self._check_rate_limits():
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "retry_after": self._get_retry_time()
                }
            
            # Wait if needed to avoid rate limiting
            if self.last_upload_time:
                time_since_last = datetime.now() - self.last_upload_time
                if time_since_last < self.upload_delay:
                    wait_time = (self.upload_delay - time_since_last).total_seconds()
                    logger.info(f"Waiting {wait_time:.0f} seconds before upload")
                    time.sleep(wait_time)
            
            # Prepare video
            processed_video_path = self._prepare_video(video_path)
            
            if not processed_video_path:
                return {
                    "success": False,
                    "error": "Failed to prepare video",
                    "file_path": str(video_path)
                }
            
            # Generate thumbnail if not provided
            if not thumbnail_path:
                thumbnail_path = self._generate_video_thumbnail(processed_video_path)
            
            # Upload the video
            logger.info(f"Uploading video: {video_path.name}")
            
            media = self.client.video_upload(
                processed_video_path,
                caption,
                thumbnail=thumbnail_path,
                extra_data=extra_data or {}
            )
            
            # Update tracking
            self.last_upload_time = datetime.now()
            self.daily_uploads += 1
            
            # Clean up processed files if they're different from originals
            if processed_video_path != video_path:
                processed_video_path.unlink(missing_ok=True)
            if thumbnail_path and thumbnail_path.parent.name == "temp":
                thumbnail_path.unlink(missing_ok=True)
            
            logger.info(f"Successfully uploaded video: {media.pk}")
            
            return {
                "success": True,
                "media_id": media.pk,
                "media_code": media.code,
                "file_path": str(video_path),
                "upload_time": self.last_upload_time.isoformat()
            }
            
        except FeedbackRequired as e:
            logger.error(f"Feedback required (possible content violation): {str(e)}")
            return {
                "success": False,
                "error": "Content feedback required",
                "details": str(e),
                "file_path": str(video_path)
            }
            
        except PleaseWaitFewMinutes:
            logger.warning("Rate limited during upload")
            return {
                "success": False,
                "error": "Rate limited", 
                "retry_after": 15 * 60,  # 15 minutes
                "file_path": str(video_path)
            }
            
        except Exception as e:
            logger.error(f"Error uploading video {video_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": str(video_path)
            }
    
    def _load_session(self) -> bool:
        """Load existing Instagram session.
        
        Returns:
            True if session loaded successfully, False otherwise
        """
        try:
            if self.session_file.exists():
                self.client.load_settings(self.session_file)
                
                # Verify session is still valid
                try:
                    self.client.get_timeline_feed()
                    return True
                except LoginRequired:
                    logger.info("Session expired, need fresh login")
                    return False
                    
            return False
            
        except Exception as e:
            logger.warning(f"Error loading session: {str(e)}")
            return False
    
    def _save_session(self) -> None:
        """Save Instagram session to file."""
        try:
            self.client.dump_settings(self.session_file)
            logger.debug(f"Session saved to {self.session_file}")
        except Exception as e:
            logger.warning(f"Error saving session: {str(e)}")
    
    def _check_rate_limits(self) -> bool:
        """Check if upload is within rate limits.
        
        Returns:
            True if within limits, False otherwise
        """
        # Reset daily counter if new day
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_uploads = 0
            self.last_reset_date = current_date
        
        return self.daily_uploads < self.max_daily_uploads
    
    def _get_retry_time(self) -> int:
        """Get time to wait before retrying upload.
        
        Returns:
            Seconds to wait
        """
        # If daily limit reached, wait until tomorrow
        if self.daily_uploads >= self.max_daily_uploads:
            tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow += timedelta(days=1)
            return int((tomorrow - datetime.now()).total_seconds())
        
        # Otherwise, standard delay
        return self.upload_delay.total_seconds()
    
    def _prepare_image(self, image_path: Path) -> Optional[Path]:
        """Prepare image for Instagram upload.
        
        Args:
            image_path: Path to original image
            
        Returns:
            Path to prepared image or None if failed
        """
        try:
            with Image.open(image_path) as img:
                # Check if image needs processing
                width, height = img.size
                file_size = image_path.stat().st_size
                
                # Instagram requirements
                max_size = config.settings.image_max_size_mb * 1024 * 1024
                min_resolution = 320
                max_resolution = 1080
                
                needs_processing = (
                    file_size > max_size or
                    width < min_resolution or height < min_resolution or
                    width > 1080 or height > 1080
                )
                
                if not needs_processing:
                    return image_path
                
                # Process image
                logger.info(f"Processing image {image_path.name}")
                
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if needed
                if width > max_resolution or height > max_resolution:
                    # Maintain aspect ratio
                    img.thumbnail((max_resolution, max_resolution), Image.Resampling.LANCZOS)
                
                # Save processed image
                temp_path = Path("temp") / f"processed_{image_path.name}"
                temp_path.parent.mkdir(exist_ok=True)
                
                # Adjust quality to meet size requirements
                quality = 95
                while quality > 50:
                    img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                    if temp_path.stat().st_size <= max_size:
                        break
                    quality -= 5
                
                return temp_path
                
        except Exception as e:
            logger.error(f"Error preparing image {image_path}: {str(e)}")
            return None
    
    def _prepare_video(self, video_path: Path) -> Optional[Path]:
        """Prepare video for Instagram upload.
        
        Args:
            video_path: Path to original video
            
        Returns:
            Path to prepared video or None if failed
        """
        try:
            file_size = video_path.stat().st_size
            max_size = config.settings.video_max_size_mb * 1024 * 1024
            
            # Check if video needs processing
            if file_size <= max_size:
                return video_path
            
            logger.info(f"Processing video {video_path.name}")
            
            # Load video
            video = mp.VideoFileClip(str(video_path))
            
            # Instagram video requirements
            max_duration = 60  # seconds
            max_resolution = 1080
            
            # Trim if too long
            if video.duration > max_duration:
                video = video.subclip(0, max_duration)
            
            # Resize if too large
            if video.h > max_resolution or video.w > max_resolution:
                video = video.resize(height=max_resolution)
            
            # Save processed video
            temp_path = Path("temp") / f"processed_{video_path.name}"
            temp_path.parent.mkdir(exist_ok=True)
            
            # Compress video to meet size requirements
            video.write_videofile(
                str(temp_path),
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                bitrate="1000k"  # Adjust bitrate for size
            )
            
            video.close()
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error preparing video {video_path}: {str(e)}")
            return None
    
    def _generate_video_thumbnail(self, video_path: Path) -> Optional[Path]:
        """Generate thumbnail for video.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Path to generated thumbnail or None if failed
        """
        try:
            video = mp.VideoFileClip(str(video_path))
            
            # Extract frame from middle of video
            middle_time = video.duration / 2
            frame = video.get_frame(middle_time)
            
            # Convert to PIL Image and save
            thumbnail_path = Path("temp") / f"thumb_{video_path.stem}.jpg"
            thumbnail_path.parent.mkdir(exist_ok=True)
            
            img = Image.fromarray(frame)
            img.save(thumbnail_path, 'JPEG', quality=90)
            
            video.close()
            
            return thumbnail_path
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return None
    
    def logout(self) -> None:
        """Logout and cleanup session."""
        try:
            self.client.logout()
            if self.session_file.exists():
                self.session_file.unlink()
            logger.info(f"Logged out {self.username}")
        except Exception as e:
            logger.warning(f"Error during logout: {str(e)}")