from typing import Any

from dify_plugin import ToolProvider


class ImageMergeProvider(ToolProvider):
    """The provider requires no credentials, so validation always succeeds."""

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        return None
