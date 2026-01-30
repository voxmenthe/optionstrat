# Redis Evaluation (Backend) - 2026-01-28

## Scope
Evaluate whether Redis is necessary in this backend, whether it is helping, and whether it can be replaced by a simpler in-memory + on-disk cache.

## Evidence (current code paths)
- Redis is used only in the market data providers as a cache layer.
  - YFinance: redis connection + cache get/set, DB fallback. `app/services/yfinance_provider.py:10-170`
  - Polygon: redis connection + cache get/set, DB fallback. `app/services/polygon_provider.py:6-166`
- On-disk cache exists already via SQLite `cache_entries`. `app/models/database.py:80-89`
- Market data service instances are created per request by FastAPI dependency injection. `app/routes/market_data.py:13-15`
- Cache test is currently skipped, so cache behavior is not validated in tests. `tests/integration_tests/test_market_data_pipeline.py:28-31`
- Redis is listed as a dependency and in env example/docs. `pyproject.toml:20`, `.env.example:8-9`, `README.md:13-18`

## Current cache behavior (as implemented)
- Providers attempt Redis at init if `REDIS_ENABLED` is true (default). If Redis fails, they fall back to SQLite.
  - Read path: Redis first; on error, disable Redis and read SQLite.
  - Write path: Redis write then return; SQLite only used if Redis fails.
  - Result: When Redis is available, the SQLite cache is not written.
- YFinance option-chain caching with Redis is effectively disabled:
  - `get_option_chain` deletes the Redis key on every call before reading the cache. `app/services/yfinance_provider.py:329-341`
  - That means with Redis enabled, option chain requests will always miss cache and re-fetch.
  - When Redis is disabled, the SQLite cache remains and can actually be reused.

## Do we really need Redis?
Short answer: No, not strictly. The code already runs without Redis by falling back to SQLite. Redis is optional and the app will function without it (though logging will warn unless `REDIS_ENABLED=false`).

## Is Redis actually helping anything?
- It helps for most cached Polygon/YFinance endpoints (ticker details, price, historical prices, etc.) by avoiding repeated external API calls, **when Redis is running**.
- It does **not** help for YFinance option chain responses because that cache is cleared on every call.
- There is no instrumentation or active test coverage confirming cache hit rates or latency improvements; cache tests are skipped.

## Can Redis be replaced by in-memory + on-disk cache?
Yes, but there are important details:
- On-disk cache already exists (SQLite `cache_entries`). You would add an in-memory TTL layer to avoid hitting SQLite on every request.
- **Provider lifetime matters**: right now `MarketDataService` (and its provider) is constructed per request. Any per-instance in-memory cache would be empty each request and provide no benefit. If you remove Redis, you need a shared in-memory cache (module-level singleton or dependency cached at app scope).
- Multi-worker or multi-instance deployments:
  - In-memory cache is per process and not shared across workers/instances.
  - SQLite is shared on disk but has limited concurrency and can become a bottleneck under load.
  - Redis provides a fast shared cache without SQLite write contention.

## Recommendation framework (choose based on deployment)
1) **Keep Redis** if you expect:
   - Multiple workers/instances or horizontal scaling
   - High request rates or tight API rate limits
   - Need for low-latency cache without SQLite contention
2) **Remove Redis** if you expect:
   - Single-instance or low-traffic usage
   - Desire for simpler ops (no extra service)
   - You are willing to rely on SQLite + a shared in-memory TTL cache

## If you keep Redis (make it less painful)
Operational friction is real, so if Redis stays, I recommend making it easy to spin up/down and easy to opt out.

**Low-effort quality-of-life changes**
- Add a tiny `scripts/redis` helper with `start`, `stop`, `status`, `logs`, `flush` that wraps Docker or `redis-server` locally.
- Add a minimal `docker-compose.redis.yml` (or dev-only compose) so `docker compose -f docker-compose.redis.yml up -d` works out of the box.
- Add a `make redis-up` / `make redis-down` (or update existing scripts) to standardize the workflow.
- Document `REDIS_ENABLED=false` as the official “no-redis” dev mode in README and `.env.example`.

**Developer ergonomics**
- Provide a health check endpoint (or CLI subcommand) that reports Redis reachable/unreachable and cache status.
- Log Redis connection failure once at startup (not on every request) to avoid noisy logs when Redis is intentionally off.
- Add a simple cache stats log in debug mode (hits/misses) to validate Redis value.

**Safer defaults**
- Default `REDIS_ENABLED` to `false` in `.env.example` for local dev, with an explicit note to enable when desired.
- When Redis is enabled but unavailable, auto-disable for the process (already done), and surface that in the health check.

## If you remove Redis (high-level outline only)
- Add a shared in-memory TTL cache (module-level or app-scoped dependency) so it persists across requests.
- Keep SQLite `cache_entries` as the persistent tier; write-through or read-through strategy to avoid losing cache after restarts.
- Update docs/env/dependencies to remove Redis requirements.
- Ensure option-chain caching logic is fixed regardless (currently Redis makes it ineffective).

## Open gaps / risks
- Cache correctness for option-chain responses is flagged as a known issue (Redis cache is explicitly cleared every call).
- No metrics on cache hit rate or latency. Without this, deciding on Redis is guesswork.
- If Redis is removed without adjusting provider lifetime, in-memory caching will be ineffective.
