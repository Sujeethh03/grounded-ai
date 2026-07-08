"""M1: fetch filings from SEC EDGAR with retry/backoff and a dead-letter path.

Not implemented yet. See CLAUDE.md and the dossier's Ledger Lens §2/§4 for the
retry policy (exponential backoff + jitter, 8 req/s ceiling matching EDGAR's
fair-access limit) and the dead-letter behavior on retry exhaustion.
"""
