"""Command-line tool to troubleshoot sprite generation and serving."""

import os
import sys
import asyncio
import aiohttp
from pathlib import Path

# Add parent directory to path to import game modules
sys.path.insert(0, os.path.dirname(__file__))

from game.sprite_generator import SpriteGenerator


async def test_sprite_files():
    """Test if sprite files exist."""
    print("\n=== Testing Sprite Files ===")
    sprite_dir = Path("static/sprites")
    if not sprite_dir.exists():
        print(f"✗ Sprite directory does not exist: {sprite_dir}")
        return
    
    print(f"✓ Sprite directory exists: {sprite_dir}")
    sprite_files = list(sprite_dir.glob("*.png"))
    print(f"Found {len(sprite_files)} PNG files:")
    for sprite_file in sprite_files:
        size = sprite_file.stat().st_size
        print(f"  - {sprite_file.name} ({size} bytes)")


async def test_static_serving():
    """Test if static files are accessible via HTTP."""
    print("\n=== Testing Static File Serving ===")
    base_url = "http://localhost:8000"
    
    # Test if server is running
    try:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{base_url}/test_sprite/1/1", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"✓ Server is running")
                        print(f"  Sprite path: {data.get('sprite_path')}")
                        print(f"  Exists: {data.get('exists')}")
                        print(f"  URL: {data.get('url')}")
                        print(f"  Full URL: {data.get('full_url')}")
                        
                        # Try to fetch the actual sprite
                        if data.get('exists'):
                            async with session.get(data.get('full_url'), timeout=aiohttp.ClientTimeout(total=2)) as img_resp:
                                if img_resp.status == 200:
                                    img_data = await img_resp.read()
                                    print(f"✓ Sprite is accessible via HTTP ({len(img_data)} bytes)")
                                else:
                                    print(f"✗ Sprite HTTP request failed: {img_resp.status}")
                        else:
                            print(f"⚠ Sprite file does not exist")
                    else:
                        print(f"✗ Server responded with status {resp.status}")
            except asyncio.TimeoutError:
                print(f"✗ Connection timeout - server may not be running")
                print(f"  Start the server with: python server.py")
                print(f"  Then run this script again to test static file serving")
            except aiohttp.ClientConnectorError as e:
                print(f"✗ Cannot connect to server: {e}")
                print(f"  Make sure the server is running on {base_url}")
                print(f"  Start the server with: python server.py")
    except Exception as e:
        print(f"✗ Error testing static serving: {e}")
        print(f"  Make sure the server is running on {base_url}")


async def test_sana_api():
    """Test Sana API endpoints."""
    print("\n=== Testing Sana API ===")
    api_base_url = "https://sana.hanlab.ai/sprint"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://sana.hanlab.ai',
        'Referer': 'https://sana.hanlab.ai/sprint/',
    }
    
    endpoints = [
        f"{api_base_url}/api/generate",
        f"{api_base_url}/generate",
        "https://sana.hanlab.ai/sprint/api/generate",
        "https://sana.hanlab.ai/api/generate"
    ]
    
    test_prompt = "pixel art sprite, simple creature, 64x64 pixels"
    payload = {
        "prompt": test_prompt,
        "size": "64x64",
        "format": "png",
        "style": "pixel art"
    }
    
    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as session:
        for endpoint in endpoints:
            try:
                print(f"\nTrying: {endpoint}")
                async with session.post(endpoint, json=payload) as resp:
                    print(f"  Status: {resp.status}")
                    print(f"  Headers: {dict(resp.headers)}")
                    if resp.status == 200:
                        content_type = resp.headers.get('Content-Type', '')
                        if 'image' in content_type:
                            data = await resp.read()
                            print(f"  ✓ Success! Received {len(data)} bytes of image data")
                            return True
                        else:
                            text = await resp.text()
                            print(f"  Response: {text[:200]}")
                    else:
                        text = await resp.text()
                        print(f"  ✗ Failed: {text[:200]}")
            except Exception as e:
                print(f"  ✗ Error: {e}")
    
    print("\n⚠ All Sana API endpoints failed. Cloudflare protection may be blocking requests.")
    return False


async def generate_test_sprite():
    """Generate a test placeholder sprite."""
    print("\n=== Generating Test Sprite ===")
    generator = SpriteGenerator()
    
    try:
        # Test placeholder generation
        sprite_data = generator._create_placeholder_sprite(999, 1)
        if sprite_data:
            sprite_path = generator._get_sprite_path(999, 1)
            async with aiofiles.open(sprite_path, 'wb') as f:
                await f.write(sprite_data)
            print(f"✓ Test sprite created: {sprite_path}")
            print(f"  Size: {len(sprite_data)} bytes")
            return True
        else:
            print("✗ Failed to create placeholder sprite")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_sprite_integrity():
    """Check if existing sprites are valid PNG files."""
    print("\n=== Checking Sprite Integrity ===")
    sprite_dir = Path("static/sprites")
    
    if not sprite_dir.exists():
        print("✗ Sprite directory does not exist")
        return
    
    sprite_files = list(sprite_dir.glob("*.png"))
    if not sprite_files:
        print("⚠ No sprite files found")
        return
    
    try:
        from PIL import Image
        for sprite_file in sprite_files:
            try:
                img = Image.open(sprite_file)
                print(f"✓ {sprite_file.name}: {img.size[0]}x{img.size[1]}, mode={img.mode}")
            except Exception as e:
                print(f"✗ {sprite_file.name}: Invalid PNG - {e}")
    except ImportError:
        print("⚠ PIL/Pillow not available, skipping integrity check")


async def main():
    """Run all troubleshooting tests."""
    print("=" * 60)
    print("Sprite Generation Troubleshooting Tool")
    print("=" * 60)
    
    # Import aiofiles here to avoid import error if not installed
    global aiofiles
    try:
        import aiofiles
    except ImportError:
        print("✗ aiofiles not installed. Run: pip install aiofiles")
        return
    
    # Run tests
    await test_sprite_files()
    await check_sprite_integrity()
    
    # Test static serving (only if server is running)
    print("\n" + "=" * 60)
    response = input("Test static file serving? (server must be running) [y/N]: ")
    if response.lower() == 'y':
        await test_static_serving()
    
    await generate_test_sprite()
    
    # Ask if user wants to test Sana API (may take time)
    print("\n" + "=" * 60)
    response = input("Test Sana API endpoints? (may take 10+ seconds) [y/N]: ")
    if response.lower() == 'y':
        await test_sana_api()
    
    print("\n" + "=" * 60)
    print("Troubleshooting complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

