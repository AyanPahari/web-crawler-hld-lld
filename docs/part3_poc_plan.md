# Engineering Plan: Proof of Concept to Production

## 1. What the POC Needs to Prove

Before committing to the full-scale architecture described in Part 2, the POC should
answer a specific set of questions that have the most bearing on whether the system
is feasible. These aren't questions about whether we *can* build a crawler — we
already have one — they're questions about whether the crawler will hold up at scale
under real-world conditions.

**The four things the POC must validate:**

1. **Throughput target is achievable.** Can we sustain ~400 URLs/second across a
   worker pool without degrading result quality? This number sounds modest, but once
   you account for per-domain rate limiting, robots.txt compliance, and retries, it
   requires careful tuning.

2. **Data quality is good enough to be useful.** TF-IDF topic extraction on
   static HTML works well for article pages (as we saw with CNN and REI). Does it
   hold up for e-commerce pages (Amazon), single-page apps, and JS-rendered content?
   Where does it fail?

3. **robots.txt compliance doesn't cripple coverage.** Aggressive crawl restrictions
   from large sites like Amazon could mean a significant chunk of the URL list is
   uncrawlable. The POC measures the actual blocked rate across a representative
   sample and informs the re-crawl strategy.

4. **The storage and query performance meets downstream needs.** Metadata written to
   PostgreSQL should be queryable at useful latency — a per-domain topic summary for
   a given month should return in under 2 seconds at 10 million records.

---

## 2. POC Scope: What We Build vs. What We Defer

The POC is explicitly not the full production system. It covers enough to validate
the four questions above and no more. This boundary matters because scope creep at
the POC stage is the most common cause of schedule slippage.

### In scope for the POC

| Component | POC version | Production version |
|-----------|-------------|-------------------|
| URL ingestion | Single text file, up to 10M URLs | Text file + MySQL, billions of URLs |
| Worker pool | 5–10 pods, fixed count | 10–200 pods, Kubernetes HPA |
| Message queue | Kafka, single broker | Kafka, 3-node cluster |
| Politeness | robots.txt + per-domain delay | Full politeness config + circuit breaker |
| Metadata store | PostgreSQL, single instance | PostgreSQL, replicated + partitioned |
| Raw HTML store | S3, no lifecycle policy | S3 with Glacier lifecycle |
| Search | Not included | Elasticsearch |
| Monitoring | Basic Prometheus + one Grafana dashboard | Full observability stack |
| Deduplication | In-memory Bloom filter (one worker) | Redis-backed Bloom filter (shared) |

### Out of scope for the POC

- Multi-region deployment
- Elasticsearch analytics layer
- Full alerting and on-call setup
- Schema migration tooling
- Cost attribution dashboards
- Re-crawl scheduling logic

The POC runs against a representative sample: 1 million URLs across 5 domains —
amazon.com, walmart.com, bestbuy.com, cnn.com, and rei.com — crawled for one month.
This is large enough to surface real bottlenecks without requiring full production
infrastructure.

---

## 3. Potential Blockers

These are risks that could derail the POC timeline or force a redesign. Each is
classified as **known** (we understand the problem, the solution path is clear) or
**uncertain** (we need to investigate before we can estimate the impact).

### 3.1 Anti-Bot Measures (Uncertain — HIGH RISK)

Large e-commerce sites, particularly Amazon and Walmart, deploy sophisticated bot
detection that goes beyond robots.txt. This includes browser fingerprinting, JavaScript
challenges, rate limiting by ASN, and CAPTCHA triggers.

**What this looks like:** Requests return HTTP 200 but the HTML body is a CAPTCHA
page or a minimal "access denied" shell rather than actual product content.

**Mitigation options:**
- Rotate User-Agent strings across realistic browser signatures
- Introduce randomized delays within the politeness window (not just fixed intervals)
- Reduce crawl rate on domains where the empty-content rate exceeds 10%
- Accept that some domains will have lower coverage and document it as a known
  limitation in the POC evaluation

**What we need to measure:** What percentage of successfully fetched pages return
actual content vs. bot-detection responses? This number drives whether we need a
more sophisticated fetch strategy before production.

### 3.2 JavaScript-Rendered Content (Known — MEDIUM RISK)

The current crawler fetches static HTML. A growing portion of the web — especially
product pages — renders meaningful content via JavaScript after the initial HTML load.
Metadata like descriptions and headings may be empty or minimal in the raw HTML.

**What this looks like:** The crawler returns a `CrawlResult` with a valid 200 status
but near-empty `body_text` and no meaningful topics, because the real content was
injected by React or a similar framework after page load.

**Mitigation options:**
- For the POC, classify these as "low-content pages" and flag them in the metadata
  (`word_count < 100` is a useful proxy)
- A headless browser tier (Playwright/Puppeteer in a separate worker pool) can
  handle JS-heavy pages in production — this is a known solved problem but adds
  significant infrastructure complexity. Defer to post-POC unless the coverage
  gap is unacceptable.

**What we need to measure:** What percentage of pages across our target domains have
`word_count < 100` after crawling? If it's under 15%, static crawling is sufficient
for the majority of use cases.

### 3.3 Kafka Partition Imbalance (Known — LOW RISK)

Partitioning Kafka by `hash(domain) % num_partitions` works well when domains are
evenly distributed. In practice, amazon.com may have 50x more URLs than a smaller
site, causing one partition to become a hotspot while others are idle.

**Mitigation:** Composite partition key (`hash(domain + url_path_prefix)`). This is
a known fix, straightforward to implement, and can be done before the first load test.

### 3.4 PostgreSQL Write Throughput at Scale (Known — MEDIUM RISK)

At 400 URLs/second, we're writing 400 rows/second to PostgreSQL. Batch inserts of
500 records bring this down to ~0.8 writes/second to the DB, which is well within
PostgreSQL's capabilities on modest hardware. However, if the batch accumulation
adds too much latency on the worker side, we may need to tune batch size or use
COPY instead of INSERT.

**What we need to measure:** End-to-end latency from fetch completion to record
committed in the DB. Target: under 5 seconds for p99.

### 3.5 Schema Evolution (Known — LOW RISK)

As we discover new metadata signals worth extracting (e.g., structured data /
JSON-LD, canonical tag reliability, hreflang), we'll need to add columns. Monthly
partitioning makes this easier — new partitions pick up the new schema, old ones
are untouched. But we still need a migration plan before production.

**Mitigation:** Add a `meta_json` JSONB column as an overflow store. New fields are
added here first (no migration required), promoted to proper columns only when usage
patterns stabilize.

---

## 4. Sprint Plan and Time Estimates

The POC runs across 6 sprints of 2 weeks each (12 weeks total). This assumes a
team of 4 engineers with the ownership split described in Section 5.

### Sprint 1 — Infrastructure Baseline (Weeks 1–2)

**Goal:** Local dev environment works end to end for a single worker against 1,000 URLs.

| Task | Owner | Estimate |
|------|-------|----------|
| Set up Kafka (single broker, Docker Compose) | Infra Eng | 3 days |
| Set up PostgreSQL with partitioning | Backend Eng 1 | 2 days |
| S3 bucket setup + IAM roles | Infra Eng | 1 day |
| Wire crawler → Kafka consumer → DB writer | Backend Eng 1 | 3 days |
| Basic Prometheus metrics on worker | Backend Eng 2 | 2 days |
| URL ingestion job (text file → Kafka) | Backend Eng 2 | 2 days |

**Exit criteria:** Single worker processes 1,000 URLs from a test file, results appear
in PostgreSQL, metrics visible in Prometheus.

---

### Sprint 2 — Politeness and Compliance (Weeks 3–4)

**Goal:** Full politeness layer working; robots.txt compliance verified and measured.

| Task | Owner | Estimate |
|------|-------|----------|
| Politeness Controller service | Backend Eng 1 | 4 days |
| Redis-backed robots.txt cache | Backend Eng 1 | 2 days |
| Per-domain rate limiter (Redis token bucket) | Backend Eng 2 | 3 days |
| Domain-override config (YAML) | Backend Eng 2 | 1 day |
| Measure blocked rate across 5 target domains | QA / Eng | 2 days |

**Exit criteria:** robots.txt compliance is 100%; domain override config works;
blocked rate report generated for all 5 target domains.

---

### Sprint 3 — Scale-Out Worker Pool (Weeks 5–6)

**Goal:** 5-pod worker fleet on Kubernetes, processing 10,000 URLs at sustained pace.

| Task | Owner | Estimate |
|------|-------|----------|
| Kubernetes deployment manifests for workers | Infra Eng | 3 days |
| Shared Redis Bloom filter for dedup | Backend Eng 2 | 2 days |
| Kafka partition rebalancing on pod scale | Backend Eng 1 | 2 days |
| Load test: 10,000 URLs, measure throughput and error rate | All | 2 days |
| Tune batch insert size for DB throughput | Backend Eng 1 | 1 day |

**Exit criteria:** 5-pod fleet sustains 50+ URLs/second; DB write p99 < 5s; no
duplicate records in PostgreSQL (dedup working).

---

### Sprint 4 — Data Quality and Topic Accuracy (Weeks 7–8)

**Goal:** Validate topic extraction quality across all page types; classify failures.

| Task | Owner | Estimate |
|------|-------|----------|
| Crawl representative 50k URL sample (10k per domain) | All | 2 days |
| Audit word_count distribution — flag low-content pages | QA / Eng | 2 days |
| Manual review of 200 random results for topic relevance | QA / Eng | 3 days |
| Add meta_json JSONB column for structured data extraction | Backend Eng 1 | 2 days |
| Document JS-rendering gap with % affected per domain | QA / Eng | 1 day |

**Exit criteria:** Topic quality rated acceptable (≥ 80% relevant on manual review)
for content-rich pages; low-content page percentage documented per domain.

---

### Sprint 5 — Full POC Load Test (Weeks 9–10)

**Goal:** Process 1 million URLs, hit throughput target, confirm system stability.

| Task | Owner | Estimate |
|------|-------|----------|
| Ingest full 1M URL test file | Backend Eng 2 | 1 day |
| Scale worker fleet to 10 pods | Infra Eng | 1 day |
| Monitor 24-hour sustained crawl | All | 2 days |
| Measure final metrics vs. SLO targets | All | 2 days |
| Grafana dashboard — crawl progress burn-down | Backend Eng 2 | 2 days |
| PostgreSQL query performance test (per-domain topic summary) | Backend Eng 1 | 2 days |

**Exit criteria:** 1M URLs processed; ≥ 99% completion rate; throughput ≥ 400 URLs/sec
at peak; DB query p99 < 2 seconds for domain summary queries.

---

### Sprint 6 — POC Evaluation and Production Readiness Plan (Weeks 11–12)

**Goal:** Document POC results, gap analysis against production requirements, go/no-go decision.

| Task | Owner | Estimate |
|------|-------|----------|
| Write POC evaluation report | Tech Lead | 3 days |
| Gap analysis: POC vs. production architecture | Tech Lead | 2 days |
| Cost projection based on POC resource usage | Infra Eng | 2 days |
| Production readiness checklist (see Section 7) | All | 2 days |
| Go/no-go decision meeting with stakeholders | All | 1 day |

**Exit criteria:** Signed-off POC evaluation report; go/no-go decision made; if go,
production sprint plan drafted.

---

## 5. Team Ownership Model

The service divides naturally into three areas. Each area has a clearly identified
owner — one person who is accountable for that area working end to end, even when
others contribute to it.

### Area 1: Crawler Core and Data Quality
**Owner: Backend Engineer 1**

Responsible for the crawler package, topic extraction logic, metadata schema, and
anything relating to the accuracy and completeness of crawled data. When a product
manager asks "why are the topics wrong for Walmart product pages?", this engineer
is the first point of contact.

Day-to-day scope: `crawler/` package, PostgreSQL schema, batch write pipeline,
topic extraction tuning, structured data parsing.

### Area 2: Infrastructure and Distributed Systems
**Owner: Infrastructure Engineer**

Responsible for Kafka setup and operations, Kubernetes worker deployment, autoscaling
configuration, S3 storage, Redis, and anything to do with the system running reliably
at scale. When workers crash or Kafka lag spikes, this is the on-call owner.

Day-to-day scope: `docker-compose.yml`, Kubernetes manifests, Kafka topics and
partitioning, S3 lifecycle policies, scaling policies, incident response runbook.

### Area 3: API, Observability, and Developer Experience
**Owner: Backend Engineer 2**

Responsible for the FastAPI service, caching layer, rate limiting, the politeness
controller, Prometheus metrics, and Grafana dashboards. Also owns the URL ingestion
pipeline (text file and MySQL reader). When the API is slow or the Grafana dashboard
shows something wrong, this is the owner.

Day-to-day scope: `api/` package, politeness controller, Redis integration,
monitoring stack, ingestion jobs.

### Tech Lead / QA
Floats across all three areas. Responsible for the overall sprint plan, cross-area
design decisions, the load test process, the POC evaluation report, and escalation
to stakeholders. In a small team, this role likely overlaps with one of the engineers
above — it's a hat, not necessarily a dedicated headcount.

---

## 6. Resource and Time Estimates

### Team

| Role | Count | Notes |
|------|-------|-------|
| Backend Engineer | 2 | Core crawler, API, ingestion |
| Infrastructure Engineer | 1 | Kafka, Kubernetes, S3 |
| Tech Lead / QA | 1 | Can be a senior backend eng wearing both hats |

**Total: 4 engineers** for the 12-week POC. This is lean — it works if scope is held
strictly to the POC boundary defined in Section 2.

### Timeline

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Sprints 1–2 | Weeks 1–4 | End-to-end pipeline working locally, compliance verified |
| Sprints 3–4 | Weeks 5–8 | Scale-out working, data quality validated |
| Sprint 5 | Weeks 9–10 | Full 1M URL load test complete |
| Sprint 6 | Weeks 11–12 | POC evaluation and go/no-go |

**Total POC duration: 12 weeks.** Post-POC production hardening (Elasticsearch,
full alerting, multi-region, re-crawl scheduling) is an estimated additional
8–10 sprints (16–20 weeks) with a team of 5–6 engineers.

### Infrastructure Costs (POC, estimated)

| Resource | Size | Monthly Cost (est.) |
|----------|------|---------------------|
| Kubernetes worker nodes (10 pods) | 2 vCPU / 4GB each, spot | ~$150–$200 |
| Kafka broker | 4 vCPU / 8GB | ~$100 |
| PostgreSQL (RDS) | db.t3.large | ~$120 |
| Redis (ElastiCache) | cache.t3.small | ~$25 |
| S3 storage (1M URLs × 50KB gzipped) | ~50 GB | ~$1.15 |
| Data transfer | Variable | ~$20–$50 |
| **Total POC** | | **~$420–$500/month** |

At full production scale (1B URLs/month), infrastructure cost grows to an estimated
$15,000–$25,000/month before spot-instance discounts, rising to S3 storage
dominating at ~$1,500–$2,000/month for raw HTML.

---

## 7. POC Evaluation Criteria

At the end of Sprint 6, the POC is evaluated against these criteria. A "go" decision
requires all four primary criteria to pass. Secondary criteria inform production
prioritization but don't block the decision.

### Primary (must pass for go decision)

| Criterion | Target | How measured |
|-----------|--------|-------------|
| Throughput | ≥ 400 URLs/sec sustained over 1 hour | Prometheus `crawler_urls_processed_total` rate |
| Completion rate | ≥ 99% of submitted URLs processed | (done / total) from ingestion job |
| Topic quality | ≥ 80% relevant on 200-item manual review | QA scorecard |
| DB query performance | Domain summary query p99 < 2 seconds | pgBench test at 10M rows |

### Secondary (inform production roadmap)

| Criterion | Acceptable range | Action if outside range |
|-----------|-----------------|------------------------|
| JS-rendered page rate | < 20% low-content pages | Prioritize headless browser tier in post-POC |
| Bot-blocked rate | < 15% of URLs | Investigate fetch strategy upgrades |
| DB write latency p99 | < 5 seconds | Tune batch size or switch to COPY |
| S3 write failure rate | < 0.5% | Check IAM permissions, retry logic |

---

## 8. Release Plan

The release plan covers the path from the current POC state to a production system
serving real users. It has three stages.

### Stage 1: Internal Beta (Weeks 13–16, post-POC)

**Who:** Internal users only (engineers, data analysts within the company)
**What:** The API endpoint is deployed to a staging environment. Internal teams can
submit URL lists of up to 100,000 URLs and query results.

- Full observability stack deployed (Prometheus, Grafana, Alertmanager)
- Runbook written for the three most likely failure modes (worker crash, Kafka lag,
  DB write failures)
- Daily crawl of a fixed 100k URL benchmark set; results compared day-over-day to
  catch regressions
- Bug bash: internal users report issues; all P1/P2 bugs fixed before Stage 2

**Exit criteria:** No P1 bugs in 7 days; 3 consecutive days of green SLO metrics.

### Stage 2: Limited External Access (Weeks 17–22, post-POC)

**Who:** 2–3 pilot customers with known, bounded URL sets
**What:** The service handles real customer URL lists under SLA. Feedback loop is
tight — customer issues are triaged within 24 hours.

- Elasticsearch tier enabled (search and analytics for pilot customers)
- Re-crawl scheduling logic deployed (freshness-based priority queue)
- On-call rotation established (4-engineer rotation, PagerDuty)
- SLA formally signed with pilot customers (based on the SLOs from Part 2)
- Cost attribution per customer tracked from day one

**Exit criteria:** Pilot customers satisfied (NPS ≥ 7/10); all SLA commitments met
for 30 consecutive days; on-call runbook validated through at least one real incident.

### Stage 3: General Availability (Week 23+, post-POC)

**Who:** All customers
**What:** Full production service, multi-region, auto-scaled to handle variable load.

- Multi-region deployment (active-passive initially, active-active after 90 days of
  stability data)
- Full documentation published: API reference, rate limits, SLAs, data schema
- Billing and usage tracking integrated
- Quarterly data retention review scheduled

**Rollback plan:** Each stage has a defined rollback trigger. For Stage 3, if the
error rate exceeds 5% for more than 10 minutes after a new deployment, the system
automatically reverts to the previous version via a Kubernetes rollout undo. A manual
rollback can be triggered by any on-call engineer using a single command.

---

## 9. Definition of a Successful Release

A release is successful if, 30 days after going live:

1. The monthly crawl job completes within the committed window
2. No customer has experienced an SLA breach
3. The on-call team has not been paged more than twice for the same root cause
   (i.e., repeat incidents are fixed, not just mitigated)
4. Topic quality scores from random sampling remain at or above the POC baseline
5. The system has processed at least one full month's URL set for at least one
   production customer

A release is **not** a success if the team is still manually intervening in the
pipeline more than once a week. Operational maturity — not just technical functionality
— is the bar.
