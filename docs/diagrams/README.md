# Architecture Diagrams

Two diagrams are provided — one for the overall system, one for the storage layer.

## Files

| File | Diagram |
|------|---------|
| `arch_diagram_1_system_overview.excalidraw` | Full system: ingest → Kafka → politeness → workers → storage → monitoring |
| `arch_diagram_2_storage_layer.excalidraw` | Storage tier breakdown: PostgreSQL, S3, Elasticsearch |

---

## How to Open in Excalidraw (recommended)

1. Go to **https://excalidraw.com**
2. Click the **folder icon** (top left) → **Open**
3. Select the `.excalidraw` file from your computer
4. The diagram loads with full editing capability
5. To export as PNG: **Menu → Export image → PNG** (set scale to 3x for high-res)

---

## How to Add Diagrams to Google Docs

**Option A — PNG embed (cleanest)**
1. Export diagrams as PNG from Excalidraw (see above)
2. In your Google Doc: **Insert → Image → Upload from computer**
3. Place the image in the doc where needed

**Option B — Diagrams.net Google Docs add-on (editable in-doc)**
1. In Google Docs: **Extensions → Add-ons → Get add-ons**
2. Search for **"Diagrams.net"** and install it
3. You can then insert and edit diagrams directly in the doc
4. Note: you'd need to recreate the diagrams in draw.io format, but the Excalidraw
   PNG exports look great embedded as images

---

## Alternative: Mermaid (for quick rendering)

If you want to render a diagram without Excalidraw, paste the Mermaid code below
at **https://mermaid.live** and export as SVG or PNG.

### Diagram 1 — System Architecture

```mermaid
flowchart LR
    A["URL Sources\n(Text file / MySQL)"] --> B["URL Normalizer\n+ Bloom Filter Dedup"]
    B --> C[("Kafka\nurl_ingest")]
    C --> D["Politeness Controller\n(robots.txt + rate limits)"]
    R[("Redis\nrobots cache")] <-.-> D
    D --> E["Crawler Workers\n(Kubernetes HPA)"]
    E --> F[("Kafka\ncrawl_results")]
    F -.->|async| C
    E --> G["Storage Layer\n(Postgres + S3 + ES)"]
    E -.->|metrics| M["Prometheus\n+ Grafana"]
```

### Diagram 2 — Storage Layer

```mermaid
flowchart TD
    W["Crawler Worker"] -->|batch INSERT| P["PostgreSQL\n(Metadata)\nPartitioned by year_month"]
    W -->|PUT gzip HTML| S["S3 / GCS\n(Raw HTML)\ndomain/year_month/hash.html.gz"]
    W -->|publish| K[("Kafka crawl_results")]
    K -->|Kafka Connect sink| E["Elasticsearch\n(Search + Analytics)"]

    P --- PN["Source of truth\n~2 TB/month"]
    S --- SN["Reprocessing source\n~5-10 TB/month gzipped"]
    E --- EN["Not source of truth\nQuery + analytics layer"]
```
