"""Content analysis module for Instagram Content Generator."""

from pathlib import Path
from typing import Dict, List, Tuple, Union

import cv2
import torch
from PIL import Image
from transformers import (
    BlipForConditionalGeneration,
    BlipProcessor,
    CLIPModel,
    CLIPProcessor,
)
from loguru import logger
import magic

from .config_manager import config


class ContentAnalyzer:
    """Analyzes images and videos to extract descriptive content."""
    
    def __init__(self):
        """Initialize content analyzer with AI models."""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing ContentAnalyzer on device: {self.device}")
        
        # Set up model cache directory
        cache_dir = Path("/app/data/model_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using model cache directory: {cache_dir}")
        
        # Initialize CLIP model for general content understanding
        logger.info("Loading CLIP model...")
        self.clip_processor = CLIPProcessor.from_pretrained(
            "openai/clip-vit-base-patch32",
            cache_dir=cache_dir
        )
        self.clip_model = CLIPModel.from_pretrained(
            "openai/clip-vit-base-patch32",
            cache_dir=cache_dir
        )
        self.clip_model.to(self.device)
        logger.info("CLIP model loaded successfully")
        
        # Initialize BLIP model for image captioning
        logger.info("Loading BLIP model...")
        self.blip_processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=cache_dir
        )
        self.blip_model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=cache_dir
        )
        self.blip_model.to(self.device)
        logger.info("BLIP model loaded successfully")
        
        # Content categories for classification
        self.content_categories = [
            "gaming", "sports", "food", "travel", "fashion", "technology",
            "nature", "lifestyle", "fitness", "art", "music", "education",
            "business", "entertainment", "pets", "cars", "photography"
        ]
    
    def analyze_file(self, file_path: Path) -> Dict[str, Union[str, List[str], float]]:
        """Analyze a media file and extract content information.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            file_type = self._detect_file_type(file_path)
            
            if file_type == "image":
                return self._analyze_image(file_path)
            elif file_type == "video":
                return self._analyze_video(file_path)
            else:
                logger.warning(f"Unsupported file type for {file_path}")
                return {"error": "Unsupported file type"}
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            return {"error": str(e)}
    
    def _detect_file_type(self, file_path: Path) -> str:
        """Detect if file is image or video.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File type: 'image', 'video', or 'unknown'
        """
        try:
            mime_type = magic.from_file(str(file_path), mime=True)
            
            if mime_type.startswith('image/'):
                return "image"
            elif mime_type.startswith('video/'):
                return "video"
            else:
                return "unknown"
                
        except Exception as e:
            logger.error(f"Error detecting file type for {file_path}: {str(e)}")
            return "unknown"
    
    def _analyze_image(self, image_path: Path) -> Dict[str, Union[str, List[str], float]]:
        """Analyze an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing image analysis results
        """
        try:
            # Load and preprocess image
            image = Image.open(image_path).convert("RGB")
            
            # Generate caption using BLIP
            caption = self._generate_image_caption(image)
            
            # Classify content category using CLIP
            category, confidence = self._classify_content(image)
            
            # Extract visual features
            visual_features = self._extract_visual_features(image)
            
            # Get image metadata
            metadata = self._get_image_metadata(image_path)
            
            return {
                "file_type": "image",
                "caption": caption,
                "category": category,
                "confidence": confidence,
                "visual_features": visual_features,
                "metadata": metadata,
                "file_path": str(image_path),
            }
            
        except Exception as e:
            logger.error(f"Error analyzing image {image_path}: {str(e)}")
            return {"error": str(e)}
    
    def _analyze_video(self, video_path: Path) -> Dict[str, Union[str, List[str], float]]:
        """Analyze a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary containing video analysis results
        """
        try:
            # Extract representative frames
            frames = self._extract_video_frames(video_path)
            
            if not frames:
                return {"error": "Could not extract frames from video"}
            
            # Analyze the middle frame as representative
            middle_frame = frames[len(frames) // 2]
            
            # Generate caption for the representative frame
            caption = self._generate_image_caption(middle_frame)
            
            # Classify content category
            category, confidence = self._classify_content(middle_frame)
            
            # Extract visual features from multiple frames
            visual_features = []
            for frame in frames[::max(1, len(frames) // 3)]:  # Sample 3 frames
                features = self._extract_visual_features(frame)
                visual_features.append(features)
            
            # Get video metadata
            metadata = self._get_video_metadata(video_path)
            
            return {
                "file_type": "video",
                "caption": caption,
                "category": category,
                "confidence": confidence,
                "visual_features": visual_features,
                "metadata": metadata,
                "frame_count": len(frames),
                "file_path": str(video_path),
            }
            
        except Exception as e:
            logger.error(f"Error analyzing video {video_path}: {str(e)}")
            return {"error": str(e)}
    
    def _generate_image_caption(self, image: Image.Image) -> str:
        """Generate a descriptive caption for an image.
        
        Args:
            image: PIL Image object
            
        Returns:
            Generated caption string
        """
        try:
            inputs = self.blip_processor(image, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                generated_ids = self.blip_model.generate(**inputs, max_length=50)
                caption = self.blip_processor.decode(generated_ids[0], skip_special_tokens=True)
            
            return caption
            
        except Exception as e:
            logger.error(f"Error generating caption: {str(e)}")
            return "Image content"
    
    def _classify_content(self, image: Image.Image) -> Tuple[str, float]:
        """Classify image content into predefined categories.
        
        Args:
            image: PIL Image object
            
        Returns:
            Tuple of (category, confidence_score)
        """
        try:
            inputs = self.clip_processor(
                text=self.content_categories,
                images=image,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.clip_model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1)
                
                max_prob_idx = probs.argmax().item()
                max_prob = probs.max().item()
                
                category = self.content_categories[max_prob_idx]
                
            return category, max_prob
            
        except Exception as e:
            logger.error(f"Error classifying content: {str(e)}")
            return "general", 0.0
    
    def _extract_visual_features(self, image: Image.Image) -> Dict[str, Union[str, int, float]]:
        """Extract visual features from an image.
        
        Args:
            image: PIL Image object
            
        Returns:
            Dictionary of visual features
        """
        try:
            # Convert to numpy array for OpenCV processing
            import numpy as np
            image_array = np.array(image)
            
            # Basic image properties
            height, width = image_array.shape[:2]
            aspect_ratio = width / height
            
            # Color analysis
            dominant_colors = self._get_dominant_colors(image_array)
            
            # Brightness and contrast
            gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
            brightness = np.mean(gray)
            contrast = np.std(gray)
            
            return {
                "width": width,
                "height": height,
                "aspect_ratio": round(aspect_ratio, 2),
                "brightness": round(brightness, 2),
                "contrast": round(contrast, 2),
                "dominant_colors": dominant_colors,
            }
            
        except Exception as e:
            logger.error(f"Error extracting visual features: {str(e)}")
            return {}
    
    def _get_dominant_colors(self, image_array, k: int = 3) -> List[str]:
        """Get dominant colors from an image.
        
        Args:
            image_array: NumPy array of image
            k: Number of dominant colors to extract
            
        Returns:
            List of dominant colors in hex format
        """
        try:
            import numpy as np
            from sklearn.cluster import KMeans
            
            # Reshape image to be a list of pixels
            pixels = image_array.reshape(-1, 3)
            
            # Use KMeans to find dominant colors
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            # Convert to hex colors
            colors = []
            for color in kmeans.cluster_centers_:
                hex_color = "#{:02x}{:02x}{:02x}".format(
                    int(color[0]), int(color[1]), int(color[2])
                )
                colors.append(hex_color)
            
            return colors
            
        except Exception as e:
            logger.error(f"Error extracting dominant colors: {str(e)}")
            return []
    
    def _extract_video_frames(self, video_path: Path, max_frames: int = 10) -> List[Image.Image]:
        """Extract frames from a video file.
        
        Args:
            video_path: Path to the video file
            max_frames: Maximum number of frames to extract
            
        Returns:
            List of PIL Image objects
        """
        try:
            cap = cv2.VideoCapture(str(video_path))
            frames = []
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_step = max(1, total_frames // max_frames)
            
            frame_idx = 0
            while len(frames) < max_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                frames.append(pil_image)
                
                frame_idx += frame_step
            
            cap.release()
            return frames
            
        except Exception as e:
            logger.error(f"Error extracting video frames: {str(e)}")
            return []
    
    def _get_image_metadata(self, image_path: Path) -> Dict[str, Union[str, int]]:
        """Get metadata from an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing metadata
        """
        try:
            stat = image_path.stat()
            
            metadata = {
                "file_size": stat.st_size,
                "created_time": stat.st_ctime,
                "modified_time": stat.st_mtime,
                "file_extension": image_path.suffix.lower(),
            }
            
            # Try to get EXIF data
            try:
                from PIL.ExifTags import TAGS
                image = Image.open(image_path)
                exif_data = image.getexif()
                
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        metadata[f"exif_{tag}"] = str(value)
            except:
                pass  # EXIF data not available or readable
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting image metadata: {str(e)}")
            return {}
    
    def _get_video_metadata(self, video_path: Path) -> Dict[str, Union[str, int, float]]:
        """Get metadata from a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary containing metadata
        """
        try:
            stat = video_path.stat()
            cap = cv2.VideoCapture(str(video_path))
            
            metadata = {
                "file_size": stat.st_size,
                "created_time": stat.st_ctime,
                "modified_time": stat.st_mtime,
                "file_extension": video_path.suffix.lower(),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "duration": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / cap.get(cv2.CAP_PROP_FPS),
            }
            
            cap.release()
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting video metadata: {str(e)}")
            return {}