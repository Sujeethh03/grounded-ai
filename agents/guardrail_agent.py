"""M5/M6: verify every claim in the synthesized answer cites a real chunk or
graph fact; trigger one revision pass, then refuse rather than return an
unsupported answer. This is the core hallucination-prevention guarantee —
see CLAUDE.md "Non-negotiables."
"""
