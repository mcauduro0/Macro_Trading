"""Central bank document scrapers with incremental caching.

Lazy imports to avoid circular dependencies at module load time.
"""


def __getattr__(name: str):
    if name == "COPOMScraper":
        from .copom_scraper import COPOMScraper

        return COPOMScraper
    if name == "FOMCScraper":
        from .fomc_scraper import FOMCScraper

        return FOMCScraper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["COPOMScraper", "FOMCScraper"]
