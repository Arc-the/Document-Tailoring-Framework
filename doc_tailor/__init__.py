from doc_tailor.graph import build_graph

# Auto-register built-in plugins
from doc_tailor.plugins.resume import register_resume_plugin
register_resume_plugin()

__all__ = ["build_graph"]
