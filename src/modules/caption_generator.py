"""Caption generation module for Instagram Content Generator."""

import re
import random
from typing import Dict, List, Optional, Union

import openai
from loguru import logger

from .config_manager import config


class CaptionGenerator:
    """Generates engaging Instagram captions based on content analysis."""
    
    def __init__(self):
        """Initialize caption generator with OpenAI client."""
        openai.api_key = config.settings.openai_api_key
        self.client = openai.OpenAI(api_key=config.settings.openai_api_key)
        
        # Popular hashtag sets by category
        self.category_hashtags = {
            "gaming": [
                "#gaming", "#gamer", "#videogames", "#esports", "#twitch",
                "#playstation", "#xbox", "#nintendo", "#pc", "#mobile",
                "#gameplay", "#streamer", "#gaminglife", "#gamingcommunity"
            ],
            "sports": [
                "#sports", "#fitness", "#workout", "#training", "#athlete",
                "#gym", "#health", "#motivation", "#fit", "#exercise",
                "#strength", "#cardio", "#running", "#cycling", "#swimming"
            ],
            "food": [
                "#food", "#foodie", "#delicious", "#yummy", "#cooking",
                "#recipe", "#chef", "#restaurant", "#foodporn", "#tasty",
                "#homemade", "#dinner", "#lunch", "#breakfast", "#healthy"
            ],
            "travel": [
                "#travel", "#wanderlust", "#adventure", "#explore", "#vacation",
                "#nature", "#photography", "#landscape", "#city", "#culture",
                "#backpacking", "#roadtrip", "#beach", "#mountains", "#sunset"
            ],
            "fashion": [
                "#fashion", "#style", "#outfit", "#ootd", "#fashionista",
                "#trendy", "#designer", "#clothing", "#accessories", "#beauty",
                "#model", "#photoshoot", "#streetstyle", "#vintage", "#luxury"
            ],
            "technology": [
                "#technology", "#tech", "#innovation", "#gadgets", "#ai",
                "#programming", "#coding", "#software", "#startup", "#digital",
                "#mobile", "#app", "#development", "#future", "#science"
            ],
            "nature": [
                "#nature", "#wildlife", "#photography", "#landscape", "#forest",
                "#ocean", "#mountains", "#sunset", "#flowers", "#trees",
                "#environment", "#conservation", "#outdoor", "#hiking", "#peace"
            ],
            "lifestyle": [
                "#lifestyle", "#life", "#happy", "#inspiration", "#motivation",
                "#positivevibes", "#selfcare", "#mindfulness", "#wellness", "#home",
                "#family", "#friends", "#love", "#joy", "#gratitude"
            ],
            "fitness": [
                "#fitness", "#workout", "#gym", "#health", "#fit", "#training",
                "#exercise", "#strength", "#muscle", "#cardio", "#bodybuilding",
                "#fitlife", "#motivation", "#goals", "#transformation"
            ],
            "art": [
                "#art", "#artist", "#creative", "#artwork", "#painting",
                "#drawing", "#design", "#illustration", "#gallery", "#museum",
                "#sculpture", "#photography", "#digital", "#creativity", "#inspiration"
            ],
            "music": [
                "#music", "#musician", "#song", "#concert", "#live", "#studio",
                "#artist", "#band", "#singer", "#guitar", "#piano", "#drums",
                "#recording", "#newmusic", "#indie", "#rock", "#pop"
            ],
            "general": [
                "#photooftheday", "#instagood", "#beautiful", "#amazing", "#cool",
                "#awesome", "#nice", "#good", "#best", "#perfect", "#great",
                "#love", "#like", "#follow", "#instadaily"
            ]
        }
        
        # Engagement prompts
        self.engagement_prompts = [
            "What do you think?",
            "Tag someone who needs to see this!",
            "Double tap if you agree!",
            "Share your thoughts below!",
            "Who can relate?",
            "What's your favorite part?",
            "Drop a ❤️ if you love this!",
            "Tell me in the comments!",
            "Save this for later!",
            "Which one is your pick?",
        ]
        
        # Emojis by category
        self.category_emojis = {
            "gaming": ["🎮", "🕹️", "🎯", "🏆", "🎊", "⚡", "🔥", "💯"],
            "sports": ["⚽", "🏀", "🏈", "🎾", "🏐", "🏆", "💪", "🔥"],
            "food": ["🍕", "🍔", "🍰", "🥘", "🍳", "🥗", "😋", "🤤"],
            "travel": ["✈️", "🌍", "🗺️", "📸", "🏔️", "🏖️", "🌅", "🎒"],
            "fashion": ["👗", "👠", "💄", "💅", "✨", "💎", "🌟", "💫"],
            "technology": ["💻", "📱", "🤖", "⚡", "🚀", "💡", "🔬", "⚙️"],
            "nature": ["🌲", "🌸", "🦋", "🌊", "🏔️", "🌅", "🌺", "🍃"],
            "lifestyle": ["☀️", "💕", "✨", "🌟", "😊", "🥰", "💖", "🌈"],
            "fitness": ["💪", "🔥", "⚡", "🏋️", "🏃", "💯", "🎯", "💥"],
            "art": ["🎨", "🖌️", "✨", "🌟", "💫", "🎭", "🖼️", "🎪"],
            "music": ["🎵", "🎶", "🎸", "🎤", "🎹", "🥁", "🎺", "🎧"],
            "general": ["✨", "💫", "🌟", "💖", "😍", "🔥", "💯", "⚡"]
        }
    
    def generate_caption(
        self, 
        analysis_result: Dict[str, Union[str, List[str], float]],
        username: Optional[str] = None,
        style: str = "engaging"
    ) -> str:
        """Generate an Instagram caption based on content analysis.
        
        Args:
            analysis_result: Content analysis results
            username: Instagram username for personalization
            style: Caption style ('engaging', 'professional', 'casual', 'funny')
            
        Returns:
            Generated Instagram caption
        """
        try:
            # Extract key information from analysis
            content_type = analysis_result.get("file_type", "image")
            description = analysis_result.get("caption", "")
            category = analysis_result.get("category", "general")
            confidence = analysis_result.get("confidence", 0.0)
            visual_features = analysis_result.get("visual_features", {})
            
            # Generate main caption using AI
            main_caption = self._generate_ai_caption(
                description, category, content_type, style, visual_features
            )
            
            # Add emojis
            caption_with_emojis = self._add_emojis(main_caption, category)
            
            # Add engagement prompt
            if random.random() < 0.7:  # 70% chance to add engagement
                engagement = random.choice(self.engagement_prompts)
                caption_with_emojis += f"\n\n{engagement}"
            
            # Add hashtags
            hashtags = self._generate_hashtags(category, description, config.settings.max_hashtags)
            final_caption = f"{caption_with_emojis}\n\n{hashtags}"
            
            # Ensure caption length is within Instagram limits
            final_caption = self._trim_caption(final_caption, config.settings.max_caption_length)
            
            logger.info(f"Generated caption for {category} content with {confidence:.2f} confidence")
            return final_caption
            
        except Exception as e:
            logger.error(f"Error generating caption: {str(e)}")
            return self._generate_fallback_caption(analysis_result)
    
    def _generate_ai_caption(
        self,
        description: str,
        category: str,
        content_type: str,
        style: str,
        visual_features: Dict
    ) -> str:
        """Generate main caption text using OpenAI API.
        
        Args:
            description: Content description from analysis
            category: Content category
            content_type: Type of content (image/video)
            style: Caption style
            visual_features: Visual features from analysis
            
        Returns:
            Generated caption text
        """
        try:
            # Build context for the AI prompt
            context_info = []
            if visual_features:
                if "dominant_colors" in visual_features:
                    colors = ", ".join(visual_features["dominant_colors"][:3])
                    context_info.append(f"dominant colors: {colors}")
                if "brightness" in visual_features:
                    brightness = "bright" if visual_features["brightness"] > 128 else "dark"
                    context_info.append(f"lighting: {brightness}")
            
            context = "; ".join(context_info) if context_info else ""
            
            # Style-specific prompts
            style_prompts = {
                "engaging": "Create an engaging, relatable Instagram caption that encourages interaction",
                "professional": "Write a professional, informative Instagram caption",
                "casual": "Write a casual, friendly Instagram caption in a conversational tone",
                "funny": "Create a humorous, entertaining Instagram caption with witty observations"
            }
            
            prompt = f"""
{style_prompts.get(style, style_prompts['engaging'])} for a {content_type} about {category}.

Content description: {description}
{f'Visual context: {context}' if context else ''}

Requirements:
- 2-4 sentences maximum
- {style} tone
- Relevant to {category} audience
- NO hashtags (they will be added separately)
- NO emojis (they will be added separately)
- Focus on the content and create value for viewers

Caption:"""
            
            response = self.client.chat.completions.create(
                model=config.settings.caption_generation_model,
                messages=[
                    {"role": "system", "content": "You are an expert Instagram content creator who writes engaging captions that drive engagement and provide value to followers."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=config.settings.caption_temperature,
            )
            
            caption = response.choices[0].message.content.strip()
            
            # Clean up the caption
            caption = re.sub(r'^Caption:\s*', '', caption)
            caption = re.sub(r'[#@]', '', caption)  # Remove any hashtags or mentions
            
            return caption
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return self._generate_simple_caption(description, category, style)
    
    def _generate_simple_caption(self, description: str, category: str, style: str) -> str:
        """Generate a simple caption without AI when API fails.
        
        Args:
            description: Content description
            category: Content category  
            style: Caption style
            
        Returns:
            Simple generated caption
        """
        style_templates = {
            "engaging": [
                f"Check out this amazing {category} content! {description}",
                f"Loving this {category} vibe! {description}",
                f"Can't get enough of {category} like this! {description}"
            ],
            "professional": [
                f"Presenting quality {category} content. {description}",
                f"Professional {category} showcase. {description}",
                f"Excellence in {category}. {description}"
            ],
            "casual": [
                f"Just some cool {category} stuff. {description}",
                f"Casual {category} vibes. {description}",
                f"Sharing some {category} love. {description}"
            ],
            "funny": [
                f"When {category} gets real! {description}",
                f"That {category} life though! {description}",
                f"Me trying to {category}... {description}"
            ]
        }
        
        templates = style_templates.get(style, style_templates["engaging"])
        return random.choice(templates)
    
    def _add_emojis(self, caption: str, category: str) -> str:
        """Add relevant emojis to the caption.
        
        Args:
            caption: Original caption text
            category: Content category
            
        Returns:
            Caption with emojis added
        """
        try:
            emojis = self.category_emojis.get(category, self.category_emojis["general"])
            
            # Add 2-4 emojis randomly throughout the caption
            sentences = caption.split('. ')
            emoji_count = random.randint(2, min(4, len(sentences)))
            
            for i in range(emoji_count):
                if i < len(sentences):
                    emoji = random.choice(emojis)
                    sentences[i] += f" {emoji}"
            
            return '. '.join(sentences)
            
        except Exception as e:
            logger.error(f"Error adding emojis: {str(e)}")
            return caption
    
    def _generate_hashtags(self, category: str, description: str, max_hashtags: int) -> str:
        """Generate relevant hashtags based on category and content.
        
        Args:
            category: Content category
            description: Content description
            max_hashtags: Maximum number of hashtags
            
        Returns:
            Hashtag string
        """
        try:
            hashtags = set()
            
            # Add category-specific hashtags
            category_tags = self.category_hashtags.get(category, [])
            hashtags.update(category_tags[:8])
            
            # Add general engagement hashtags
            general_tags = self.category_hashtags["general"]
            hashtags.update(random.sample(general_tags, min(5, len(general_tags))))
            
            # Extract keywords from description for additional hashtags
            description_keywords = self._extract_keywords(description)
            for keyword in description_keywords[:3]:
                hashtags.add(f"#{keyword.lower().replace(' ', '')}")
            
            # Limit to max hashtags
            final_hashtags = list(hashtags)[:max_hashtags]
            
            return " ".join(final_hashtags)
            
        except Exception as e:
            logger.error(f"Error generating hashtags: {str(e)}")
            return " ".join(self.category_hashtags.get(category, ["#photooftheday"])[:10])
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract potential keywords from text for hashtags.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of extracted keywords
        """
        try:
            # Simple keyword extraction
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            
            # Filter out common words
            stop_words = {
                'the', 'and', 'are', 'this', 'that', 'with', 'for', 'was', 'were',
                'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should',
                'can', 'may', 'might', 'must', 'shall', 'not', 'but', 'from',
                'image', 'video', 'content', 'photo', 'picture'
            }
            
            keywords = [word for word in words if word not in stop_words]
            
            # Return unique keywords, limited to reasonable number
            return list(dict.fromkeys(keywords))[:5]
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            return []
    
    def _trim_caption(self, caption: str, max_length: int) -> str:
        """Trim caption to fit Instagram's character limit.
        
        Args:
            caption: Original caption
            max_length: Maximum allowed length
            
        Returns:
            Trimmed caption
        """
        if len(caption) <= max_length:
            return caption
        
        # Try to trim at sentence boundaries first
        sentences = caption.split('. ')
        trimmed = ""
        
        for sentence in sentences:
            if len(trimmed + sentence + '. ') <= max_length - 3:  # Leave space for "..."
                trimmed += sentence + '. '
            else:
                break
        
        if trimmed:
            return trimmed.rstrip() + "..."
        
        # If even one sentence is too long, trim at word boundaries
        words = caption.split()
        trimmed_words = []
        
        for word in words:
            if len(' '.join(trimmed_words + [word])) <= max_length - 3:
                trimmed_words.append(word)
            else:
                break
        
        return ' '.join(trimmed_words) + "..."
    
    def _generate_fallback_caption(self, analysis_result: Dict) -> str:
        """Generate a simple fallback caption when all else fails.
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            Fallback caption
        """
        category = analysis_result.get("category", "general")
        content_type = analysis_result.get("file_type", "content")
        
        fallback_texts = [
            f"Amazing {category} {content_type}! ✨",
            f"Check this out! 🔥 #{category}",
            f"Loving this {category} vibe! 💫",
            f"Beautiful {content_type} 📸 #{category}"
        ]
        
        caption = random.choice(fallback_texts)
        hashtags = " ".join(self.category_hashtags.get(category, ["#photooftheday"])[:10])
        
        return f"{caption}\n\n{hashtags}"