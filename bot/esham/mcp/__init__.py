"""Esham MCP (Model Context Protocol) Paketi.

BIST (Borsa İstanbul) ve TÜRİB (ELÜS - Elektronik Ürün Senedi) piyasalarını
birleştiren kurumsal AI asistan MCP sunucusu.
"""
from .server import mcp, run_server

__all__ = ["mcp", "run_server"]
