"""Re-export — usar app.services.wordpress_adapter."""
from app.services.wordpress_adapter import (
    MockWordPressAdapter,
    WordPressAdapter,
    WordPressRestAdapter,
    get_wordpress_adapter,
    publish_proposal,
)

__all__ = [
    "MockWordPressAdapter",
    "WordPressAdapter",
    "WordPressRestAdapter",
    "get_wordpress_adapter",
    "publish_proposal",
]
