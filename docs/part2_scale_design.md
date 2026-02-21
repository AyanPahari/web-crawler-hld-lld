# Scale Design: Operationalizing a Crawler for Billions of URLs

## Overview

The core crawler built in Part 1 works well for a single URL. Scaling it to process
billions of URLs — spread across domains like amazon.com, walmart.com, and bestbuy.com
for a given month — requires rethinking every layer: how URLs are ingested, how work
is distributed across machines, how fetched content is stored, and how the system
behaves when things go wrong.

This document covers the end-to-end architecture for running this at scale, along with
the storage schema, politeness strategy, SLOs, and monitoring approach.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            URL INGESTION LAYER                              │
│                                                                             │
│  Text file / MySQL  ──►  URL Normalizer  ──►  Dedup Filter  ──►  Kafka     │
│  (billions of URLs)       (canonicalize)       (Bloom filter)    Topic:    │
│                                                                  url_queue  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SCHEDULER / POLITENESS LAYER                      │
│                                                                             │
│  Politeness Controller                                                      │
│  - Reads robots.txt per domain (cached 24h in Redis)                       │
│  - Enforces per-domain crawl delay                                         │
│  - Groups URLs by domain, respects Crawl-Delay directive                   │
│  - Emits to per-domain partitioned Kafka topics                            │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CRAWLER WORKERS                                │
│                                                                             │
│  Worker Pool (auto-scaled on Kubernetes)                                   │
│  Each worker:                                                              │
│  1. Polls its assigned domain partition                                    │
│  2. Fetches HTML (connection pool, retry with backoff)                     │
│  3. Parses metadata + extracts topics (TF-IDF)                             │
│  4. Writes result to Storage Layer                                         │
│  5. Emits metrics + commits Kafka offset                                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE LAYER                                  │
│                                                                             │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│  │  PostgreSQL       │   │  S3 / GCS Bucket │   │  Elasticsearch         │  │
│  │  (metadata store) │   │  (raw HTML store)│   │  (search + analytics)  │  │
│  │  Partitioned by   │   │  Key: domain/    │   │  Index: crawl_metadata  │  │
│  │  year_month       │   │  year_month/hash │   │                        │  │
│  └──────────────────┘   └──────────────────┘   └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. URL Ingestion

### Input Sources

The system accepts URLs from two sources as described in the requirements:

**Text file (batch)**
Large `.txt` files (one URL per line) are uploaded to S3/GCS. An ingestion job reads
them in chunks of 100k, normalizes each URL, checks it against a Bloom filter, and
publishes valid candidates to Kafka. This job runs as a Kubernetes batch Job.

**MySQL (scheduled)**
For month-based crawl jobs (e.g., "all amazon.com URLs for July"), a cron-triggered
job queries the MySQL table, applies the same normalization + dedup, and streams
records to Kafka. The query is paginated using keyset pagination (not OFFSET) to
avoid performance degradation at scale.

```sql
-- example MySQL source table
CREATE TABLE url_queue (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    url         VARCHAR(2048) NOT NULL,
    domain      VARCHAR(255)  NOT NULL,
    year_month  CHAR(7)       NOT NULL,  -- e.g. '2024-07'
    status      ENUM('pending','processing','done','failed') DEFAULT 'pending',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_domain_month (domain, year_month),
    INDEX idx_status (status)
);
```

### URL Normalization

Before anything is queued, URLs go through a normalization step:
- Lowercase scheme and host
- Remove tracking parameters (`utm_*`, `ref`, `fbclid`, etc.)
- Strip trailing slashes consistently
- Resolve relative paths
- Canonicalize to HTTPS where available

### Deduplication

A domain-partitioned Bloom filter running in Redis provides fast O(1) dedup.
False positive rate is tuned to ~0.1% — acceptable given the scale. URLs that
pass the Bloom filter are also checked against a "recently crawled" index (URLs
crawled within the last N days are skipped unless a re-crawl is explicitly requested).

---

## 3. Kafka Topic Design

```
Topics:
  url_ingest          — raw URLs from ingestion jobs (all domains, high throughput)
  url_scheduled       — politeness-controlled, per-domain partitioned
  crawl_results       — completed crawl results for downstream consumers
  crawl_failures      — failed URLs for retry or dead-letter handling
  robots_cache_miss   — domains whose robots.txt needs refreshing
```

**Partitioning strategy for `url_scheduled`:** partition by `hash(domain) % num_partitions`.
This ensures all URLs for a given domain are processed by the same worker, making
per-domain rate limiting trivial — no cross-worker coordination needed.

**Retention:** `url_ingest` and `url_scheduled` use 7-day retention. `crawl_results`
is retained for 30 days to allow downstream consumers to replay if needed.

---

## 4. Politeness and robots.txt Compliance

Respecting crawl etiquette is not optional — aggressive crawling can get the service
IP-blocked, trigger legal issues, and damage the reputation of the crawl infrastructure.

### robots.txt Handling

- On first encounter with a domain, the Politeness Controller fetches `/robots.txt`
  and caches the parsed result in Redis with a 24-hour TTL.
- The crawler checks `can_fetch(our_user_agent, url)` before every request.
- Disallowed URLs are moved to the `crawl_failures` topic with reason `robots_disallowed`
  rather than silently dropped, so they can be reported.
- If a `Crawl-Delay` directive is present, it's respected as a floor delay between
  requests to that domain.

### Per-Domain Rate Limiting

Even for domains that don't specify a crawl delay, we apply a configurable default
minimum gap between requests to the same domain. This is enforced at the worker level
using a per-domain Redis key with an expiry equal to the desired delay.

```
Default delays:
  General sites:    1 request / 2 seconds
  E-commerce sites: 1 request / 5 seconds  (higher load, stricter bots)
  News sites:       1 request / 3 seconds
```

These are configurable per domain in a YAML config file, allowing operators to tune
without redeploying workers.

### Retry and Backoff

- HTTP 429 or 503: exponential backoff starting at 30s, max 3 retries.
- HTTP 5xx: retry up to 2 times with a 10s delay.
- Connection timeout: retry once after 15s, then move to dead-letter.
- HTTP 4xx (except 429): no retry — URL is marked `failed` with the status code.

---

## 5. Storage Design

### 5.1 PostgreSQL — Metadata Store

The primary structured store for crawl results. Partitioned by `year_month` to keep
query performance predictable as the dataset grows.

```sql
-- main metadata table, partitioned by year_month
CREATE TABLE crawl_metadata (
    id              BIGSERIAL,
    url             TEXT        NOT NULL,
    url_hash        CHAR(16)    NOT NULL,   -- sha256 prefix for fast lookup
    domain          VARCHAR(255) NOT NULL,
    final_url       TEXT,
    status_code     SMALLINT    NOT NULL,
    crawled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    year_month      CHAR(7)     NOT NULL,   -- '2024-07'

    -- standard metadata
    title           TEXT,
    description     TEXT,
    keywords        TEXT,
    author          VARCHAR(512),
    language        CHAR(10),
    canonical_url   TEXT,

    -- open graph
    og_title        TEXT,
    og_description  TEXT,
    og_image        TEXT,
    og_type         VARCHAR(64),

    -- derived
    topics          TEXT[],                 -- top 15 TF-IDF terms
    word_count      INTEGER DEFAULT 0,

    -- storage reference
    raw_html_path   TEXT,                   -- S3/GCS path to raw HTML

    -- error tracking
    error_message   TEXT,
    retry_count     SMALLINT DEFAULT 0,

    PRIMARY KEY (id, year_month)
) PARTITION BY LIST (year_month);

-- partition per month created automatically by the ingestion job
CREATE TABLE crawl_metadata_2024_07 PARTITION OF crawl_metadata
    FOR VALUES IN ('2024-07');

-- indexes on the partition (applied to all partitions via the parent)
CREATE INDEX ON crawl_metadata (url_hash, year_month);
CREATE INDEX ON crawl_metadata (domain, crawled_at);
CREATE INDEX ON crawl_metadata USING GIN (topics);
```

**Why partitioning?** Each monthly partition is independent. Old partitions can be
archived, dropped, or moved to cheaper storage without touching live data. Queries
scoped to a month (`WHERE year_month = '2024-07'`) hit only one partition.

**Why `url_hash` instead of indexing the full URL?** URLs can be several hundred
characters. A 16-char hash prefix gives fast equality lookups at a fraction of the
index size. Collisions are practically impossible at this prefix length.

### 5.2 S3 / GCS — Raw HTML Store

Parsed metadata is cheap to re-extract, but raw HTML is not cheap to re-fetch.
The full HTML of every crawled page is stored in object storage for reprocessing.

```
Key structure: s3://crawler-html/{domain}/{year_month}/{url_hash}.html.gz

Example:
  s3://crawler-html/amazon.com/2024-07/a3f2b1c4d5e6f7a8.html.gz
```

Files are gzip-compressed (typically 5-15x reduction for HTML). A lifecycle policy
moves objects to Glacier / coldline storage after 90 days.

### 5.3 Elasticsearch — Search and Analytics

A copy of the metadata (without raw HTML) is written to Elasticsearch for:
- Full-text search across titles, descriptions, and topics
- Aggregations (e.g., "top topics across walmart.com in July 2024")
- Near-realtime querying by downstream consumers

The Kafka `crawl_results` topic feeds a Kafka Connect sink that streams records
into Elasticsearch asynchronously. The ES index is not the source of truth — that
remains PostgreSQL.

---

## 6. Configurability

The crawler is designed to be config-driven rather than code-driven for operational
parameters. A YAML config file (one per environment) controls the key knobs:

```yaml
crawl:
  default_crawl_delay_seconds: 2
  max_retries: 3
  fetch_timeout_seconds: 15
  max_content_bytes: 5242880     # 5 MB
  user_agent: "BrightEdgeCrawler/1.0 (+https://brightedge.com/crawler)"

politeness:
  robots_cache_ttl_hours: 24
  domain_overrides:
    amazon.com:
      crawl_delay_seconds: 5
    walmart.com:
      crawl_delay_seconds: 5

workers:
  concurrency_per_pod: 50        # async fetch slots per worker pod
  pod_count_min: 10
  pod_count_max: 200             # HPA upper bound

storage:
  metadata_db_url: "${METADATA_DB_URL}"
  html_bucket: "crawler-html"
  html_bucket_region: "us-east-1"
  cache_url: "${REDIS_URL}"
  cache_ttl_seconds: 3600

topics:
  top_n: 15
  ngram_range: [1, 2]
```

Workers pick up config at startup. For domain override changes, a SIGHUP causes the
worker to reload config without restarting, so delay changes take effect within seconds.

---

## 7. Reliability and Fault Tolerance

### Worker Crashes

Workers commit Kafka offsets only after successfully writing to the storage layer.
If a worker dies mid-processing, the uncommitted messages are re-delivered to another
worker. Exactly-once semantics are approximated via the `url_hash + year_month`
unique constraint in PostgreSQL — duplicate writes are idempotent (INSERT ON CONFLICT
DO UPDATE).

### Storage Failures

If the metadata DB is unavailable, the worker stops committing offsets and pauses
consumption. Kafka retains messages for 7 days, giving plenty of time to recover
without losing work.

If S3 writes fail, the metadata record is still written to PostgreSQL with
`raw_html_path = NULL`. A background reconciliation job periodically finds these
records and re-uploads HTML from a local worker cache (if still available).

### Cascading Failures

A circuit breaker per domain prevents one slow domain from blocking workers.
If a domain's fetch error rate exceeds 50% over a 5-minute window, that domain is
temporarily suspended and its remaining queue is paused. An alert fires for operator
review.

---

## 8. Throughput and Capacity Estimates

For reference at the design scale of ~1 billion URLs per month:

| Metric | Value |
|--------|-------|
| URLs per month | 1,000,000,000 |
| Seconds in a month | ~2,592,000 |
| Required sustained throughput | ~386 URLs/second |
| Average fetch time (p50) | 1.5 seconds |
| Workers needed at 50 concurrent fetches/pod | ~12 pods |
| Workers with 2x headroom | ~25 pods |
| Storage for metadata (avg 2KB/record) | ~2 TB/month |
| Storage for raw HTML at 50KB avg (gzipped) | ~50 TB/month |

25 worker pods is well within Kubernetes autoscaling range. S3 costs at 50 TB/month
are manageable with lifecycle policies (Glacier after 90 days drops cost ~75%).

---

## 9. SLOs and SLAs

These targets apply to a production deployment processing the full monthly URL set.

### SLOs (internal targets)

| Objective | Target |
|-----------|--------|
| Crawl completion rate | ≥ 99% of submitted URLs processed within the crawl window |
| Metadata write success rate | ≥ 99.5% of fetched pages produce a stored record |
| API availability (`/crawl` endpoint) | ≥ 99.9% over 30-day rolling window |
| API p99 latency (per-URL crawl) | ≤ 10 seconds |
| API p50 latency | ≤ 2 seconds |
| Cache hit ratio | ≥ 40% for repeated URL queries |
| robots.txt compliance | 100% — zero violations |
| Deduplication accuracy | ≥ 99.9% (Bloom filter false positive rate ≤ 0.1%) |

### SLAs (external commitments to consumers)

| Commitment | Value |
|------------|-------|
| Monthly crawl job completion | Within 30 days of job submission |
| Data freshness for a given URL | Metadata available within 24h of successful fetch |
| API uptime | 99.9% monthly |
| Data retention | Metadata retained for 18 months; raw HTML for 12 months |
| Incident response | P1 (data pipeline down) within 1 hour; P2 within 4 hours |

### Error Budget

At 99.9% availability, the monthly error budget is ~43 minutes of downtime.
Anything beyond that triggers a post-mortem and freeze on non-critical deployments.

---

## 10. Monitoring Metrics and Tooling

### Tooling Stack

| Layer | Tool |
|-------|------|
| Metrics collection | Prometheus |
| Dashboards | Grafana |
| Alerting | Alertmanager → PagerDuty |
| Distributed tracing | Jaeger (sampled at 5%) |
| Log aggregation | ELK stack (Elasticsearch + Logstash + Kibana) |
| Synthetic monitoring | Scheduled probe jobs against the `/crawl` API |

### Key Metrics

**Throughput and Progress**
- `crawler_urls_processed_total` — counter, labeled by `domain` and `status` (success/failed/skipped)
- `crawler_urls_queued_total` — size of the Kafka `url_scheduled` topic lag
- `crawler_crawl_duration_seconds` — histogram of end-to-end crawl time per URL
- `crawler_monthly_completion_percent` — gauge: URLs done / URLs total for current month

**Fetch Quality**
- `crawler_http_response_total` — counter labeled by `status_code` and `domain`
- `crawler_robots_blocked_total` — counter of URLs blocked by robots.txt
- `crawler_retries_total` — counter labeled by retry reason
- `crawler_fetch_timeout_total` — counter of timed-out fetches

**Storage**
- `crawler_db_write_duration_seconds` — histogram of PostgreSQL insert latency
- `crawler_s3_write_duration_seconds` — histogram of S3 put latency
- `crawler_cache_hit_ratio` — gauge: cache hits / total API requests
- `crawler_db_partition_row_count` — gauge per `year_month` partition

**Worker Health**
- `crawler_worker_active_fetches` — gauge per pod
- `crawler_worker_error_rate` — rate of exceptions per pod
- `kafka_consumer_lag` — standard Kafka metric via JMX exporter

### Grafana Dashboard Panels

1. **Crawl Progress** — URLs processed vs. total target (monthly burn-down chart)
2. **Throughput** — URLs/second over time, broken down by domain
3. **HTTP Status Codes** — stacked bar of 200/4xx/5xx/timeout over time
4. **Domain Health** — table of top 20 domains with success rate and current delay
5. **Worker Fleet** — active workers, CPU/memory, active fetch slots per pod
6. **Queue Depth** — Kafka consumer lag across partitions
7. **Storage Latency** — DB + S3 write p50/p99 over time
8. **Error Breakdown** — robots blocks, timeouts, retries, parse failures

### Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| Pipeline stalled | `crawler_urls_processed_total` rate = 0 for 5 min | P1 |
| High failure rate | Error rate > 10% over 15 min | P1 |
| Kafka lag growing | Consumer lag increasing for > 30 min | P2 |
| Worker fleet shrinking | Active pods < `pod_count_min` | P2 |
| DB write latency | p99 > 5 seconds for > 10 min | P2 |
| Disk / S3 budget | Monthly S3 cost forecast > 120% of budget | P3 |
| Low cache hit ratio | Cache hits < 20% for > 1 hour | P3 |

---

## 11. Cost Optimization

A few structural choices keep costs under control at this scale:

**Spot / preemptible instances for workers.** Crawler workers are stateless —
Kafka offsets are not committed until work is written to storage, so a spot
instance termination just causes a re-delivery. Running workers on spot instances
can cut compute costs by 60-70%.

**HTML compression.** Storing raw HTML gzipped on S3 at 5-15x compression ratio
dramatically reduces storage costs. For 1 billion pages at 50KB average → ~50 TB
uncompressed vs ~5-10 TB compressed.

**Tiered storage.** S3 lifecycle policies move raw HTML to Glacier after 90 days.
Metadata older than 18 months is archived to Parquet files on S3 and dropped from
PostgreSQL, keeping the active DB size bounded.

**Batch writes to PostgreSQL.** Workers accumulate results in memory and flush in
batches of 500 records, significantly reducing DB connection overhead and write
amplification compared to one-insert-per-crawl.

**Selective re-crawling.** Not every URL needs to be re-crawled every month.
A freshness score (based on content change frequency) determines crawl priority.
Frequently updated pages (news sites) crawled weekly; stable pages (product listings)
crawled monthly; near-static pages (about pages) quarterly.
