"""M2: detect SEC form/XBRL schema drift and fall back to a best-effort parser.

Not implemented yet. On a miss against the known schema, flag the filing
ingestion_status = 'schema_drift_flagged' (see dossier DB schema) rather than
silently mis-parsing it.
"""
