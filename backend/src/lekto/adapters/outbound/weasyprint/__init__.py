"""Mails set as PDF with WeasyPrint (HTML and CSS, no browser, nothing from the network)."""

from lekto.adapters.outbound.weasyprint.renderer import WeasyPrintMailRenderer

__all__ = ["WeasyPrintMailRenderer"]
