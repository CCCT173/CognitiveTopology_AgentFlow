"""内置工具包"""
from app.tools.builtin.rag_search import RagSearchTool
from app.tools.builtin.web_search import WebSearchTool
from app.tools.builtin.http_request import HttpRequestTool
from app.tools.builtin.calculator import CalculatorTool
from app.tools import registry

# 注册内置工具
registry.register(RagSearchTool())
registry.register(WebSearchTool())
registry.register(HttpRequestTool())
registry.register(CalculatorTool())
