"""Metadata reader and page composer adapters: pikepdf for PDFs, Pillow for images."""

from lekto.adapters.outbound.pikepdf.composer import PikepdfPageComposer
from lekto.adapters.outbound.pikepdf.metadata import FileMetadataReader

__all__ = ["FileMetadataReader", "PikepdfPageComposer"]
