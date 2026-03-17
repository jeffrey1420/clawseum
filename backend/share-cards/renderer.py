"""
CLAWSEUM Share Card Renderer
Converts HTML templates to PNG images using Playwright
"""

import asyncio
import hashlib
import base64
from pathlib import Path
from typing import Optional, Union
from playwright.async_api import async_playwright


class CardRenderer:
    """Renders HTML share cards to PNG images"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the card renderer
        
        Args:
            cache_dir: Directory to cache generated images (default: ./cache)
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / "cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self._browser = None
        self._playwright = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def start(self):
        """Start the browser instance"""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
    
    async def close(self):
        """Close the browser instance"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    def _get_cache_key(self, html_content: str) -> str:
        """Generate cache key from HTML content"""
        return hashlib.sha256(html_content.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key"""
        return self.cache_dir / f"{cache_key}.png"
    
    async def render(
        self,
        html_content: str,
        output_path: Optional[str] = None,
        return_base64: bool = False,
        use_cache: bool = True
    ) -> Union[str, bytes]:
        """
        Render HTML to PNG image
        
        Args:
            html_content: HTML string to render
            output_path: Optional file path to save the image
            return_base64: If True, return base64 encoded string instead of path
            use_cache: If True, use cached version if available
            
        Returns:
            File path to the generated PNG, or base64 string if return_base64=True
        """
        # Check cache first
        cache_key = self._get_cache_key(html_content)
        cache_path = self._get_cache_path(cache_key)
        
        if use_cache and cache_path.exists():
            if output_path:
                # Copy from cache to output path
                import shutil
                shutil.copy(cache_path, output_path)
                result_path = output_path
            else:
                result_path = str(cache_path)
            
            if return_base64:
                with open(result_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
            return result_path
        
        # Ensure browser is started
        if self._browser is None:
            await self.start()
        
        # Create a new page
        page = await self._browser.new_page(viewport={'width': 1200, 'height': 675})
        
        try:
            # Set content and wait for it to load
            await page.set_content(html_content, wait_until='networkidle')
            
            # Small delay to ensure animations/styles are applied
            await asyncio.sleep(0.5)
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=False
            )
            
            # Determine output path
            if output_path:
                final_path = Path(output_path)
            else:
                final_path = cache_path
            
            # Write to file
            final_path.parent.mkdir(exist_ok=True, parents=True)
            with open(final_path, 'wb') as f:
                f.write(screenshot_bytes)
            
            # Also write to cache if not already there
            if output_path and use_cache and not cache_path.exists():
                with open(cache_path, 'wb') as f:
                    f.write(screenshot_bytes)
            
            if return_base64:
                return base64.b64encode(screenshot_bytes).decode()
            
            return str(final_path)
            
        finally:
            await page.close()
    
    async def render_card(
        self,
        html_content: str,
        card_type: str,
        output_dir: Optional[str] = None,
        return_base64: bool = False
    ) -> Union[str, bytes]:
        """
        Convenience method to render a card with automatic naming
        
        Args:
            html_content: HTML string to render
            card_type: Type of card (e.g., 'betrayal', 'victory')
            output_dir: Directory to save the image (default: ./output)
            return_base64: If True, return base64 encoded string
            
        Returns:
            File path to the generated PNG, or base64 string if return_base64=True
        """
        if output_dir is None and not return_base64:
            output_dir = Path(__file__).parent / "output"
            Path(output_dir).mkdir(exist_ok=True, parents=True)
        
        if output_dir:
            import time
            timestamp = int(time.time())
            output_path = Path(output_dir) / f"{card_type}_{timestamp}.png"
        else:
            output_path = None
        
        return await self.render(
            html_content,
            output_path=str(output_path) if output_path else None,
            return_base64=return_base64
        )


# Synchronous wrapper for easier use
class SyncCardRenderer:
    """Synchronous wrapper around CardRenderer"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.renderer = CardRenderer(cache_dir)
        self._loop = None
    
    def _get_loop(self):
        """Get or create event loop"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    def render(self, *args, **kwargs):
        """Synchronous render method"""
        loop = self._get_loop()
        return loop.run_until_complete(self.renderer.render(*args, **kwargs))
    
    def render_card(self, *args, **kwargs):
        """Synchronous render_card method"""
        loop = self._get_loop()
        return loop.run_until_complete(self.renderer.render_card(*args, **kwargs))
    
    def __enter__(self):
        loop = self._get_loop()
        loop.run_until_complete(self.renderer.start())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        loop = self._get_loop()
        loop.run_until_complete(self.renderer.close())
