"""Legal corpus ingest for the companion sales model (cycle 2 mouth).

Does not train weights, approve knowledge cards, or download books.
"""

from .ingest import ingest_sales_corpus, corpus_status

__all__ = ["ingest_sales_corpus", "corpus_status"]
