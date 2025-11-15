"""SpriteGenerator class for generating pixel art sprites using Sana API."""

import os
import aiohttp
import aiofiles
import hashlib
from pathlib import Path
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor


class SpriteGenerator:
    """Generate pixel art sprites for creatures using Sana API."""
    
    def __init__(self, api_base_url: str = "https://sana.hanlab.ai/sprint", sprite_dir: str = "static/sprites"):
        """
        Initialize sprite generator.
        
        Args:
            api_base_url: Base URL for Sana API (Gradio app)
            sprite_dir: Directory to store generated sprites
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.sprite_dir = Path(sprite_dir)
        self.sprite_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = aiohttp.ClientTimeout(total=30)  # Gradio can take longer
        self.executor = ThreadPoolExecutor(max_workers=2)  # For running sync Gradio client
    
    def _get_sprite_path(self, creature_id: int, stage: int, format: str = "png") -> Path:
        """Get file path for sprite."""
        filename = f"{creature_id}_{stage}.{format}"
        return self.sprite_dir / filename
    
    def _get_sprite_url(self, creature_id: int, stage: int, format: str = "png") -> str:
        """Get URL path for sprite."""
        filename = f"{creature_id}_{stage}.{format}"
        return f"/static/sprites/{filename}"
    
    def _sprite_exists(self, creature_id: int, stage: int, format: str = "png") -> bool:
        """Check if sprite already exists."""
        sprite_path = self._get_sprite_path(creature_id, stage, format)
        return sprite_path.exists()
    
    def _create_placeholder_sprite(self, creature_id: int, stage: int) -> Optional[bytes]:
        """
        Create a simple placeholder sprite as fallback.
        Returns PNG bytes of a colored square.
        """
        try:
            from PIL import Image, ImageDraw
            
            # Create a 64x64 image
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))  # Transparent background
            draw = ImageDraw.Draw(img)
            
            # Draw a simple colored circle/square based on creature ID
            colors = [
                (33, 150, 243, 255),  # Blue
                (244, 67, 54, 255),   # Red
                (76, 175, 80, 255),   # Green
                (255, 235, 59, 255), # Yellow
            ]
            color = colors[(creature_id - 1) % len(colors)]
            
            # Draw a circle
            margin = 8
            draw.ellipse([margin, margin, 64-margin, 64-margin], fill=color)
            
            # Add stage indicator (smaller circle inside)
            if stage > 1:
                inner_margin = 20
                draw.ellipse([inner_margin, inner_margin, 64-inner_margin, 64-inner_margin], 
                           fill=(255, 255, 255, 200))
            
            # Convert to bytes
            import io
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            return img_bytes.getvalue()
        except ImportError:
            print(f"[SpriteGenerator] PIL/Pillow not available for placeholder sprites")
            return None
        except Exception as e:
            print(f"[SpriteGenerator] Error creating placeholder: {e}")
            return None
    
    def _create_prompt(self, user_prompt: str, stage: int) -> str:
        """
        Create formatted prompt for Sana API.
        
        Args:
            user_prompt: Original user description
            stage: Evolution stage (1, 2, or 3)
            
        Returns:
            Formatted prompt string
        """
        stage_descriptions = {
            1: "simple single-celled organism",
            2: "multicellular colony organism",
            3: "complex organism with specialized parts"
        }
        stage_desc = stage_descriptions.get(stage, "creature")
        
        prompt = f"pixel art sprite, {stage_desc}, {user_prompt}, 64x64 pixels, simple style, game character, top-down view, transparent background"
        return prompt
    
    def _generate_sprite_sync(self, api_prompt: str) -> Optional[bytes]:
        """
        Synchronously generate sprite using Gradio client.
        This runs in a thread pool to avoid blocking.
        
        Args:
            api_prompt: Formatted prompt for image generation
            
        Returns:
            Image bytes or None if generation fails
        """
        try:
            from gradio_client import Client
            
            print(f"[SpriteGenerator] Connecting to Gradio API: {self.api_base_url}")
            client = Client(self.api_base_url)
            
            print(f"[SpriteGenerator] Calling /run API with prompt: {api_prompt[:100]}...")
            try:
                result = client.predict(
                    prompt=api_prompt,
                    style="Pixel art",  # Use Pixel art style
                    num_imgs=1,
                    seed=0,
                    height=64,  # 64x64 for sprites
                    width=64,
                    guidance_scale=4.5,
                    num_inference_steps=2,
                    max_timesteps="1.5708",  # Must be string, not float
                    intermediate_timesteps="1.3",  # Must be string
                    timesteps=None,
                    randomize_seed=True,
                    use_resolution_binning=True,
                    api_name="/run"
                )
            except Exception as param_error:
                # If parameter error, try with minimal parameters
                if "not in the list of choices" in str(param_error) or "AppError" in type(param_error).__name__:
                    print(f"[SpriteGenerator] Parameter error, retrying with minimal params: {param_error}")
                    result = client.predict(
                        prompt=api_prompt,
                        style="Pixel art",
                        height=64,
                        width=64,
                        api_name="/run"
                    )
                else:
                    raise
            
            print(f"[SpriteGenerator] API returned result type: {type(result)}")
            print(f"[SpriteGenerator] Result length: {len(result) if result else 0}")
            
            # Result is a tuple: (images, seed, value_10, value_4)
            # images is a list of dicts with image data
            if result and len(result) > 0:
                images = result[0]
                print(f"[SpriteGenerator] Images type: {type(images)}, length: {len(images) if images else 0}")
                
                if images and len(images) > 0:
                    image_data = images[0]
                    print(f"[SpriteGenerator] Image data type: {type(image_data)}")
                    print(f"[SpriteGenerator] Image data: {str(image_data)[:200]}...")
                    
                    # Image dict has 'image' key with 'url' or 'path'
                    if isinstance(image_data, dict):
                        img_info = image_data.get('image', {})
                        print(f"[SpriteGenerator] Image info type: {type(img_info)}")
                        
                        if isinstance(img_info, dict):
                            # Try to get image URL or path
                            image_url = img_info.get('url')
                            image_path = img_info.get('path')
                            
                            print(f"[SpriteGenerator] Image URL: {image_url}, Path: {image_path}")
                            
                            if image_url:
                                print(f"[SpriteGenerator] Downloading image from URL: {image_url}")
                                # Download image from URL
                                import requests
                                response = requests.get(image_url, timeout=30)
                                if response.status_code == 200:
                                    print(f"[SpriteGenerator] ✓ Downloaded {len(response.content)} bytes")
                                    return response.content
                                else:
                                    print(f"[SpriteGenerator] ✗ Download failed: {response.status_code}")
                            elif image_path:
                                print(f"[SpriteGenerator] Reading image from path: {image_path}")
                                # Read from local path
                                if os.path.exists(image_path):
                                    with open(image_path, 'rb') as f:
                                        data = f.read()
                                        print(f"[SpriteGenerator] ✓ Read {len(data)} bytes from file")
                                        return data
                                else:
                                    print(f"[SpriteGenerator] ✗ File does not exist: {image_path}")
                        elif isinstance(img_info, str):
                            # Might be a direct file path
                            print(f"[SpriteGenerator] Image info is string (path): {img_info}")
                            if os.path.exists(img_info):
                                with open(img_info, 'rb') as f:
                                    return f.read()
            
            print(f"[SpriteGenerator] ✗ No image data found in API response")
            print(f"[SpriteGenerator] Full result structure: {result}")
            return None
            
        except ImportError:
            print(f"[SpriteGenerator] ✗ gradio_client not installed. Run: pip install gradio_client")
            return None
        except Exception as e:
            error_type = type(e).__name__
            print(f"[SpriteGenerator] ✗ Error generating sprite with Gradio API ({error_type}): {e}")
            
            
            import traceback
            traceback.print_exc()
            return None
    
    async def generate_sprite(
        self, 
        user_prompt: str, 
        creature_id: int, 
        stage: int,
        force_regenerate: bool = False
    ) -> Optional[str]:
        """
        Generate sprite for a creature.
        
        Args:
            user_prompt: User's original creature description
            creature_id: Unique creature identifier
            stage: Evolution stage (1, 2, or 3)
            force_regenerate: If True, regenerate even if sprite exists
            
        Returns:
            Sprite URL path (e.g., "/static/sprites/1_1.png") or None if generation fails
        """
        # Check cache first
        if not force_regenerate and self._sprite_exists(creature_id, stage):
            print(f"[SpriteGenerator] Using cached sprite for creature {creature_id} stage {stage}")
            return self._get_sprite_url(creature_id, stage)
        
        try:
            # Format prompt for API
            api_prompt = self._create_prompt(user_prompt, stage)
            print(f"[SpriteGenerator] Generating sprite for creature {creature_id} stage {stage}")
            print(f"[SpriteGenerator] User prompt: {user_prompt[:100]}...")
            print(f"[SpriteGenerator] API prompt: {api_prompt[:100]}...")
            print(f"[SpriteGenerator] API base URL: {self.api_base_url}")
            
            # Call Sana API using Gradio client
            # Run sync Gradio client in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            sprite_data = await loop.run_in_executor(
                self.executor,
                self._generate_sprite_sync,
                api_prompt
            )
            
            if not sprite_data:
                print(f"[SpriteGenerator] ✗ Failed to generate sprite with Gradio API")
                print(f"[SpriteGenerator] → Creating placeholder sprite as fallback")
                # Create a simple placeholder sprite
                sprite_data = self._create_placeholder_sprite(creature_id, stage)
                if not sprite_data:
                    print(f"[SpriteGenerator] → Placeholder creation also failed, will use canvas drawing")
                    return None
                print(f"[SpriteGenerator] ✓ Placeholder sprite created successfully")
            
            # Save sprite to file
            sprite_path = self._get_sprite_path(creature_id, stage)
            async with aiofiles.open(sprite_path, 'wb') as f:
                await f.write(sprite_data)
            
            print(f"[SpriteGenerator] ✓ Sprite saved to {sprite_path}")
            return self._get_sprite_url(creature_id, stage)
                
        except aiohttp.ClientTimeout:
            print(f"[SpriteGenerator] ✗ Timeout generating sprite (exceeded {self.timeout.total}s)")
            print(f"[SpriteGenerator] → Falling back gracefully (creature will use canvas drawing)")
            return None
        except aiohttp.ClientError as e:
            print(f"[SpriteGenerator] ✗ Network error generating sprite: {e}")
            print(f"[SpriteGenerator] → Falling back gracefully (creature will use canvas drawing)")
            return None
        except Exception as e:
            print(f"[SpriteGenerator] ✗ Unexpected error generating sprite: {e}")
            import traceback
            traceback.print_exc()
            print(f"[SpriteGenerator] → Falling back gracefully (creature will use canvas drawing)")
            return None
    
    async def get_or_generate_sprite(
        self,
        user_prompt: str,
        creature_id: int,
        stage: int
    ) -> Optional[str]:
        """
        Get existing sprite or generate new one.
        
        Args:
            user_prompt: User's original creature description
            creature_id: Unique creature identifier
            stage: Evolution stage (1, 2, or 3)
            
        Returns:
            Sprite URL path or None if generation fails
        """
        # Check if sprite exists
        if self._sprite_exists(creature_id, stage):
            return self._get_sprite_url(creature_id, stage)
        
        # Generate new sprite
        return await self.generate_sprite(user_prompt, creature_id, stage)

