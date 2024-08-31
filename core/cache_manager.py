import os

class CacheManager:
    CACHE_DIR = "resources"

    @staticmethod
    def get_cached_path(filename):
        return os.path.join(CacheManager.CACHE_DIR, filename)

    @staticmethod
    def is_cached(filename):
        return os.path.exists(CacheManager.get_cached_path(filename))
