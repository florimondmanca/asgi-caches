from caches import Cache

cache = Cache("locmem://default", ttl=2 * 60)
special_cache = Cache("locmem://special", ttl=60)
