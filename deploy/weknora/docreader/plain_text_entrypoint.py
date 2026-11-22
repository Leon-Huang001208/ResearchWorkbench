"""Add TXT to pinned f17ee8a8 DocReader after its original crypto entrypoint.

Mount this file read-only and replace only the command passed to the existing
container_entrypoint.py. That entrypoint retains the ARM/OpenSSL startup probe.
The compatibility overlay changes parser registration, never original bytes.
"""

import logging
import runpy

from docreader.models.document import Document
from docreader.parser.base_parser import BaseParser
from docreader.parser.registry import registry

logger = logging.getLogger(__name__)


class PlainTextParser(BaseParser):
    """Extract strict UTF-8 text without interpreting links, images or markup."""

    def parse_into_text(self, content: bytes) -> Document:
        try:
            text = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            logger.warning("rwb_docreader_txt_invalid_utf8")
            raise ValueError("Plain-text content must use valid UTF-8") from None
        if not text.strip():
            logger.warning("rwb_docreader_txt_empty")
            raise ValueError("Plain-text content is empty")
        logger.info("rwb_docreader_txt_parsed bytes=%d characters=%d", len(content), len(text))
        return Document(content=text)


def install_plain_text_parser() -> None:
    """Narrowly extend the pinned private mapping; preserve existing parsers."""
    engines = getattr(registry, "_engines", None)
    builtin = engines.get("builtin") if isinstance(engines, dict) else None
    if not isinstance(builtin, dict):
        logger.error("rwb_docreader_txt_registry_incompatible")
        raise RuntimeError(  # noqa: TRY004 - pinned runtime contract, not caller input.
            "Pinned DocReader builtin parser registry is unavailable"
        )
    if "txt" not in builtin:
        builtin["txt"] = PlainTextParser
        logger.info("rwb_docreader_txt_parser_registered")


def main() -> None:
    install_plain_text_parser()
    runpy.run_module("docreader.main", run_name="__main__")


if __name__ == "__main__":
    main()
