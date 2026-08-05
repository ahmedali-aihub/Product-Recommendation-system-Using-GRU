# Session-Based E-Commerce Recommender

Predicts **what a user will click or buy next**, based on their current session's
behavior — not their long-term profile. This mirrors how modern feeds (Instagram,
Flipkart, TikTok) re-rank content in real time as a user interacts, rather than
relying on a static "users who liked X also liked Y" matrix.

> **Core question the model answers:** given what this user just viewed/clicked
> in this session, what are they most likely to want next?

---

## Table of Contents

- [1. Problem Statement](#1-problem-statement)
- [2. Dataset](#2-dataset)
- [3. Tech Stack](#3-tech-stack)
- [4. System Architecture](#4-system-architecture)
- [5. Repository Layout](#5-repository-layout)
- [6. Data Pipeline (Offline)](#6-data-pipeline-offline)
- [7. Model](#7-model)
- [8. Evaluation](#8-evaluation)
- [9. Serving Layer (Online)](#9-serving-layer-online)
- [10. Cold-Start Extension (Stretch)](#10-cold-start-extension-stretch)
- [11. Key Design Decisions & Why](#11-key-design-decisions--why)
- [12. Project Roadmap](#12-project-roadmap)
- [13. Results](#13-results)

---

## 1. Problem Statement

Session-based recommendation treats user behavior as a **sequence problem**
rather than a matrix-completion problem. The model doesn't need to know who a
user is long-term — it only needs the ordered list of items they've interacted
with in the current session to predict the next one. This makes it work for
anonymous or brand-new users, which classic collaborative filtering cannot
handle well.

**Stretch extension:** handle brand-new products with zero click history
(cold-start) by understanding what the product *looks like*, using image
embeddings instead of past behavior.

---

## 2. Dataset

**Primary:** [eCommerce behavior data from multi category store](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store)
(Kaggle, REES46 Marketing Platform)

- 285M+ real events across `view`, `cart`, `purchase`
- Fields: `event_time`, `event_type`, `product_id`, `category_id`,
  `category_code`, `brand`, `price`, `user_id`, `user_session`
- **Scope: one month only** (`2019-Oct.csv`, ~42M events, ~5.5GB uncompressed)
  — the full multi-month dataset is unnecessary and impractical for a first
  build. Even one month is too large to load naively into pandas; see
  [Section 6](#6-data-pipeline-offline) for how ingestion is handled.
- **Working slice: 20M rows** (`2019-Oct-subset20M.csv`), bulk-loaded into
  MySQL. Measured stats on the loaded data:

  | Metric | Value |
  |---|---|
  | Total events | 20,000,000 |
  | Distinct sessions | 4,301,849 |
  | Sessions with only 1 event (dropped, nothing to predict) | 1,479,884 |
  | Usable sessions (>1 event) | 2,821,965 |
  | Distinct products | 141,694 |
  | Training pairs generated (before length-percentile cap) | ~15,698,151 |

  The `<OTHER>`-token vocabulary (Section 6d) keeps the top ~40K products
  by frequency — about 28% of distinct product *ids*, but the large
  majority of *events*, since traffic is concentrated in a long-tail
  distribution typical of e-commerce catalogs.

**Cold-start extension data:** REES46 ships **no product images** — only
`category_code`, `brand`, `price`. The image-based cold-start demo therefore
either scrapes a small image sample or uses a separate public dataset (e.g.
Amazon Berkeley Objects). This is called out explicitly because it means the
cold-start demo is illustrative on a secondary catalog, not a seamless
extension of the same REES46 product IDs — see [Section 10](#10-cold-start-extension-stretch).

---

## 3. Tech Stack

| Layer | Tool |
|---|---|
| Data storage | MySQL 8.0 (`events` table — source of truth, append target for new data) |
| Data ingestion | MySQL `LOAD DATA INFILE` (bulk load, not row-by-row `INSERT`) |
| Data processing | Python, Pandas (working format: Parquet, exported per training run) |
| Sequence modeling | TensorFlow/Keras (GRU4Rec baseline) — stretch: PyTorch (SASRec, Transformer-based) |
| Image embeddings (stretch) | CLIP or a pretrained ResNet (via `torchvision`) |
| Vector search (stretch) | FAISS |
| Backend / serving | FastAPI |
| Frontend / storefront | React (Vite), Tailwind CSS + shadcn/ui, Framer Motion |
| Experiment tracking (optional) | MLflow or structured logging |

---

## 4. System Architecture

Three stages, deliberately separated — storage (MySQL, source of truth),
offline pipeline (slow, produces artifacts), and online serving (fast,
stateless, just a forward pass). This mirrors how real production
recommenders are structured: raw data lands in a database, training runs
periodically against it, and serving never retrains on the request path.

```
┌───────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                             │
│                                                                     │
│   Raw CSV ──LOAD DATA INFILE──▶  MySQL `events` table               │
│                                   (source of truth,                 │
│                                    append target for new data)      │
└───────────────────────────────────────┬─────────────────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────┐
│                         OFFLINE PIPELINE                           │
│         (runs once, then re-triggered periodically / on demand)    │
│                                                                     │
│  Query MySQL for training window                                   │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐      │
│  │ Export to   │───▶│ Session      │───▶│ Vocabulary +       │      │
│  │ Parquet     │    │ builder      │    │ sequence encoding  │      │
│  └─────────────┘    └──────────────┘    └────────┬───────────┘      │
│                                                    │                 │
│                                                    ▼                 │
│                                          ┌───────────────────┐      │
│                                          │ Train/val/test    │      │
│                                          │ split (time-based)│      │
│                                          └────────┬──────────┘      │
│                                                    │                 │
│                                                    ▼                 │
│                                          ┌───────────────────┐      │
│                                          │ GRU4Rec model     │      │
│                                          │ training (Keras)  │      │
│                                          └────────┬──────────┘      │
│                                                    │                 │
│                                                    ▼                 │
│                                     model.h5 + item_vocab.json      │
└─────────────────────────────────────────┬───────────────────────────┘
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────┐
│                          ONLINE PIPELINE                           │
│                       (runs on every request)                      │
│                                                                     │
│   React storefront ──HTTP──▶ FastAPI /predict ──▶  loaded model    │
│   (browsing session         (session seq in,        (in-memory,    │
│    so far, e.g. cart/        top-N items out)        hot-reloaded  │
│    recently viewed)                                   after retrain)│
└───────────────────────────────────────────────────────────────────┘
```

**Feedback / retrain loop:** serving is stateless — a live user session never
triggers training; it only reads the model already loaded in memory. New
events are appended to the MySQL `events` table (batched, not row-by-row),
and retraining happens on a separate schedule, decoupled from `/predict`.

Retraining is a **hybrid of two strategies**, not a single "retrain on
everything" job — on CPU, a from-scratch retrain whose training set grows
forever (yesterday's history + today's + ...) would eventually take longer
than the schedule allows:

| Strategy | Trains on | Cost | Cadence |
|---|---|---|---|
| **Sliding-window full retrain** | From-scratch, on a *fixed-size* rolling window (e.g. most recent 30-45 days) — old data ages out as new data comes in, so training set size never grows unbounded | Hours (bounded, same every cycle) | Periodic, e.g. weekly |
| **Warm-start fine-tune** | Previous checkpoint's weights (`model.load_weights(...)`, not random init), continued for a few epochs on just the newly accumulated batch, low learning rate | Minutes | Frequent, e.g. daily / every N new events |

The full retrain corrects drift and prevents the warm-start fine-tunes from
compounding into catastrophic forgetting; the warm-start keeps the model from
going stale in between. Both produce the same `model.h5`/`item_vocab.json`
artifacts, and the running FastAPI process hot-reloads them from disk (behind
a lock) without a restart — so the React storefront reflects the updated
model on its next `/predict` call. *(This loop is the target design; see
[Section 12](#12-project-roadmap) for what's actually implemented at each
phase.)*

---

## 5. Repository Layout

```
product-recommendation-project/
├── data/
│   ├── raw/                  # downloaded 2019-Oct.csv (gitignored, too big)
│   ├── interim/               # cleaned events, session-filtered
│   └── processed/             # encoded sequences ready for training (.npy/.parquet)
├── db/
│   ├── schema.sql             # MySQL `events` table definition + indexes
│   ├── load_data.sql          # LOAD DATA INFILE bulk-load script
│   └── products_schema.sql    # `products`/`carts`/`cart_items` tables (storefront v1)
├── src/
│   ├── data/
│   │   ├── db.py               # MySQL connection helper (reads .env for credentials)
│   │   ├── export.py           # query MySQL training window → Parquet
│   │   ├── sessions.py        # group by user_session, sort, build sequences
│   │   ├── vocab.py           # top-N product vocab, <OTHER>/<PAD>/<UNK> tokens
│   │   ├── split.py           # time-based train/val/test split
│   │   └── build_product_catalog.py  # events → products (generated names/icons, storefront v1)
│   ├── model/
│   │   ├── gru4rec.py         # Keras model definition
│   │   ├── train.py           # training loop, checkpointing
│   │   └── evaluate.py        # Recall@10, NDCG@10, coverage, popularity baseline
│   ├── serving/
│   │   ├── main.py             # FastAPI app, CORS, router registration
│   │   ├── schemas.py          # Pydantic request/response models
│   │   └── routers/
│   │       ├── products.py     # GET /api/products, /api/products/{id}
│   │       ├── categories.py   # GET /api/categories
│   │       └── cart.py         # GET/POST/PATCH/DELETE /api/cart/... (session-based, no login)
│   │       # predict.py (future) -- /predict slots in here once GRU4Rec is trained
│   └── config.py              # paths, hyperparams, constants (vocab size, etc.)
├── app/                        # React (Vite) storefront: browse, product detail, cart
│   └── src/
│       ├── api/client.js       # fetch wrapper, cart-id/localStorage handling
│       ├── pages/               # ProductListPage, ProductDetailPage, CartPage
│       └── components/          # Navbar, ProductCard, CategoryFilterBar, Pagination
├── notebooks/
│   ├── 01_explore.ipynb       # scratch EDA only — pipeline logic lives in src/
│   └── 02_model_prototype.ipynb  # annotated GRU4Rec build/train/eval on a 1-day slice;
│                                  # every concept explained inline before promoting to src/model/
├── models/
│   ├── gru4rec.weights.h5
│   └── item_vocab.json
├── tests/
│   └── test_sessions.py       # at least one test on session-building edge cases
├── requirements.txt
└── README.md
```

Notebooks are for exploration only. All logic that needs to run repeatably
(ingest, session-building, training) lives in `src/` as modules — this is
what separates an engineered pipeline from "a notebook someone cleaned up."

---

## 6. Data Pipeline (Offline)

### 6a. Storage & ingest (`db/schema.sql`, `db/load_data.sql`)
The raw CSV is bulk-loaded into a MySQL `events` table via `LOAD DATA INFILE`
— **not** row-by-row `INSERT`, which would take hours at 42M+ rows. This
table is the source of truth: new events (from the simulated feedback loop,
or a future real ingestion source) are appended here in batches, not
individually.

Indexes on `user_session` and `event_time` are added after the bulk load
(building indexes during a 42M-row load is slower than loading first, then
indexing). `category_code`/`brand` nulls are kept as-is in MySQL — cleaning
and type-casting decisions happen at export time, not in storage, so the
database always holds the raw truth.

### 6b. Export (`src/data/export.py`)
Training doesn't query MySQL repeatedly — that would make the database the
bottleneck on every experiment. Instead, each training run queries MySQL
once for its target time window and exports the result to Parquet, which
pandas/TensorFlow then read directly. MySQL is the append-friendly system of
record; Parquet is the fast, immutable working format for a given training
run.

### 6c. Session building (`src/data/sessions.py`)
Group by `user_session`, sort each group by `event_time`, collapse to an
ordered list of `product_id`s per session. Filters applied:
- Drop sessions with only 1 event (nothing to predict from).
- Cap session length at a chosen percentile (e.g. 95th) — a handful of
  pathological sessions with thousands of events would otherwise dominate
  padding/batch cost.

### 6d. Vocabulary (`src/data/vocab.py`)
Count product frequency across the training window. Keep the top-N most
frequent products (e.g. 30k–50k) as real tokens; map everything else to a
shared `<OTHER>` token. Reserve token IDs for `<PAD>` (padding shorter
sequences) and `<UNK>` (products never seen in training, encountered at
inference).

This truncation is a **deliberate scoping decision**, not an oversight: a
dense softmax over the dataset's full catalog (hundreds of thousands of
distinct products) is slow and memory-heavy for no accuracy benefit at this
project's scale. It's paired with sampled softmax at training time
(Section 7) — vocab truncation shrinks *how big* the output space is, sampled
softmax shrinks *how much of it gets scored per step*; both target the same
CPU bottleneck from different angles.

### 6e. Sequence encoding
Convert each session's product list into integer IDs via the vocab. Each
session generates multiple `(input_prefix, target_next_item)` training pairs
— e.g. session `[A, B, C, D]` yields `(A→B)`, `(A,B→C)`, `(A,B,C→D)`. Sequences
are padded/truncated to a fixed max length.

### 6f. Time-based split (`src/data/split.py`)
Sessions are sorted by start time. The last ~3 days become the test set, the
few days before that the validation set, everything earlier is training data.
Random splitting is deliberately avoided — it would let the model "see the
future" during training and inflate metrics artificially.

---

## 7. Model

```
Input: padded sequence of item IDs, shape (batch, max_len)
   │
   ▼
Embedding layer (vocab_size × embed_dim, mask_zero=True for padding)
   │
   ▼
GRU layer → context vector (final hidden state, one per session-so-far)
   │
   ├── TRAINING:  tf.nn.sampled_softmax_loss(context, true item + N random
   │               negatives) — scores ~100 items, not the full vocab
   │
   └── EVAL / SERVING:  context @ output_weights.T + bias → full logits
                          over vocab_size → top-10 (exact, no sampling)
```

**Sampled softmax, not plain softmax, from the start.** A dense softmax over
even a truncated ~40K-item vocabulary, computed on every one of ~15M training
pairs, is the dominant cost of training on CPU (see the epoch-time discussion
in [Section 13](#13-results)) — the output-layer matmul alone accounts for
the large majority of it. Sampled softmax scores the true next item plus a
small random sample (~100) of negatives instead of the full vocabulary,
giving an unbiased-in-expectation estimate of the same gradient at a small
fraction of the cost. This isn't a later optimization — it's the baseline
architecture, because CPU-only training makes the full-softmax cost
impractical to iterate on. Full (non-sampled) logits are computed only where
exactness actually matters: evaluation and serving, never inside the
training loop. There, output ids are looked up against `output_weights` /
`output_bias`, plain trainable variables shared between the sampled-softmax
training path and the full-logits eval path — not a `Dense` + `softmax`
layer — since `tf.nn.sampled_softmax_loss` needs direct access to those raw
weight/bias tensors, which doesn't fit a standard Keras `(y_true, y_pred)`
loss. This means training uses a custom `tf.GradientTape` loop rather than
`model.fit(...)`. See `notebooks/02_model_prototype.ipynb` for the full
implementation with every design choice explained inline.

One detail worth calling out because it's a real (not incidental) design
coupling: `tf.nn.sampled_softmax_loss`'s default sampler assumes class ids
are roughly ordered by descending frequency — which is exactly how
`src/data/vocab.py` assigns ids (id 3 = most frequent product, and so on).
The vocab was built that way specifically so it lines up with what sampled
softmax expects.

**Documented upgrade path:** a pairwise ranking loss (BPR-max, as in the
original GRU4Rec paper) is a further refinement over sampled softmax, or
swap the architecture for a Transformer-based model (SASRec) — closer to
what modern production systems (e.g. Meta's HSTU) use.

---

## 8. Evaluation

For each test session's prefix, the model's top-10 predicted next items are
checked against:

| Metric | What it tells you |
|---|---|
| Recall@10 | Was the actual next item somewhere in the top 10 predictions? |
| NDCG@10 | Same as Recall@10, but rewards ranking the correct item *higher* |
| Coverage | Is the model just recommending the same popular items to everyone, or genuinely personalizing? |

Plain accuracy is deliberately avoided — it's the wrong metric for a ranking
problem and would make a mediocre model look artificially good.

**Popularity baseline:** a "always recommend the globally top-10 most-viewed
items" baseline is computed on the same test set. The GRU4Rec model's
Recall@10 is reported alongside it — beating this baseline is what makes the
evaluation credible; a model that merely matches it hasn't learned anything
session-specific.

---

## 9. Serving Layer (Online)

### 9a. Storefront API (`src/serving/`) — built now, ahead of the model
Built as v1 of the product-facing site, deliberately decoupled from the ML
timeline so the storefront doesn't block on full-scale training (see
Section 11):

- **`GET /api/products`** (paginated, optional `category` filter) and
  **`GET /api/products/{id}`** — backed by a `products` table
  (`db/products_schema.sql`), *derived* from `events` rather than sourced
  elsewhere: REES46 has no product names or images, only
  `product_id`/`category_code`/`brand`/`price`.
  `src/data/build_product_catalog.py` reduces the 20M+ event rows down to
  one row per distinct product (141,694 of them), generates a display
  name from the real `category_code`/`brand` fields (e.g.
  `"Samsung Smartphone"`), and an icon key the frontend maps to a static
  placeholder image — every product shown is a real `product_id` that a
  future recommendation could point to, not a synthetic catalog layered
  on top.
- **`GET /api/categories`** — top-level categories with product counts,
  for the storefront's nav/filter.
- **`GET/POST/PATCH/DELETE /api/cart/...`** — a cart is identified by a
  client-generated UUID (`X-Cart-Id` header, stored in the browser's
  `localStorage`), not a logged-in user. No accounts in v1: this keeps
  serving fully stateless per request, and gives the future
  recommendation endpoint a natural, already-existing anchor for "this
  session" without needing a login system that session-based
  recommendation was never going to need anyway.

### 9b. `POST /predict` (`src/serving/routers/predict.py`) — built, running on a small-scale model
Loads `gru4rec.weights.h5` and `item_vocab.json` once at import time (not
per-request) via the `load_model()` helper in `src/model/gru4rec.py`.
Accepts `{product_ids: [...], top_k}` — the session so far, oldest to most
recent — encodes them via the vocab (a product not in the top-N vocab
maps to `<OTHER>`, the same fallback `encode_sequence` already uses at
training time, not `<UNK>` — the two are only distinguishable with
training-time frequency data this serving code doesn't retain), runs a
forward pass, and decodes the top-N logits back to real `product_id`s via
`full_logits()` (exact scores, no sampling — see Section 7). Results are
joined against the `products` table so the response is full `ProductOut`
objects the frontend can render directly, in the model's ranking order
(not SQL's arbitrary row order). Handles an empty session (`{"items": []}`,
no error) and product IDs never seen in training.

**Honesty note on model quality:** the currently-loaded weights are from a
1M-row training run (`python -m src.model.train --limit 1000000`, the
practical prototyping-scale cycle chosen for this hardware — see Section
4's hybrid retrain strategy), not the full 20M-row dataset. Measured on a
held-out test set: **Recall@10 = 0.4502, NDCG@10 = 0.3291**, a 5.3x
improvement over the popularity baseline (0.0855) — real, working
recommendations, not placeholder, with more headroom available from a
full-scale run. A fresh training run's weights only take effect after the
backend process restarts; there's no live file-watching hot-reload yet (a
simplification versus the target design in Section 4).

### React (Vite) storefront (`app/`)
Product listing with category browsing and pagination, a product detail

### React (Vite) storefront (`app/`)
Product listing with category browsing and search, a product detail page,
and a cart drawer (add/update quantity/remove, opens from anywhere via
the navbar) — against the API in 9a. No login, no checkout, matching the
v1 scope.

A **"You might also like" section** (`RecommendationsSection.jsx`) now
appears on both the product detail page and the cart drawer, calling
`/predict` live. Its input is the current session, tracked client-side
with no login (`app/src/lib/sessionHistory.js` — a rolling list of
recently-viewed product IDs in `localStorage`, capped at 10) on the
product page, or the cart's current contents in the drawer — this is the
actual demo payoff described in Section 9 turned real, not a mockup.

Styled with **Tailwind CSS + shadcn/ui** (component source lives in
`app/src/components/ui/`, generated via the shadcn CLI, owned/editable —
not a black-box dependency), light/dark theme via CSS variables and a
small custom `ThemeProvider` context (no `next-themes`, since this isn't
Next.js), and **Framer Motion** for the interactive polish: the cart
drawer's spring-in, staggered product grid reveal on load, and hover
micro-interactions on product cards.

**Product photography** (`app/public/images/{category}/`): REES46 ships
no product photos, only `category_code`/`brand`/`price` — same underlying
gap Section 10 describes for cold-start embeddings, but a different
problem (this is *display* imagery, not a similarity-search embedding).
`app/scripts/fetch_product_images.py` is a one-time script (stdlib only,
not a recurring pipeline step) that pulls 8 curated, editorial-style
photos per top-level category from the Pexels API. `app/src/lib/productImage.js`
then deterministically assigns each product one photo from its category's
pool, based on `product_id` — the same product always shows the same
photo, and the 8-photo pool rotates across every product in that
category. Stated plainly: real photography, category-representative, not
a unique photo per SKU, since that data doesn't exist for this dataset.

---

## 10. Cold-Start Extension (Stretch)

Since REES46 provides no product images, this is best understood as a
**secondary, smaller pipeline** rather than a natural extension of the main
system:

1. Source images for a subset of products (scrape a small sample, or use a
   separate image dataset like Amazon Berkeley Objects as an illustrative
   demo rather than a true integration with REES46 product IDs).
2. Run CLIP (or a pretrained ResNet) to get an embedding per product image.
3. Store embeddings in FAISS.
4. In the API: if a `product_id` has no click history (not present in the
   trained vocab), fall back to FAISS nearest-neighbor image search instead
   of the GRU.

**Honesty note:** if the image dataset used doesn't share product IDs with
REES46, this section of the README should say so plainly — it's a simulated
cold-start demo, not a seamless fallback on the same live catalog.

---

## 11. Key Design Decisions & Why

These are the decisions most likely to get questioned by a technical
reviewer — stated here explicitly rather than left implicit:

- **Storefront built before the full-scale model, not after**: the
  product-facing site (browse, cart) doesn't depend on GRU4Rec being
  trained at full scale, so it was built and shipped first rather than
  waiting on a multi-hour/day training run. `/predict` slots into the
  same FastAPI app as another router later, behind the same API surface
  — the storefront's product/cart pages don't need to change when it
  lands, only gain a new section that calls it.
- **Product catalog derived from `events`, not a separate synthetic
  one**: REES46 ships no product names or images, so the storefront's
  `products` table is generated from the real `category_code`/`brand`
  fields (`src/data/build_product_catalog.py`) rather than a decorative
  fake catalog — every product shown is a real `product_id` a future
  recommendation will point to, keeping the honesty principle from
  Section 10 consistent across the whole project, not just the
  cold-start section.
- **Cart identified by a client-side id, not a login**: no accounts in
  v1, both because it's out of scope and because session-based
  recommendation (Section 1) was never going to need one — a login
  system would have been complexity in service of nothing this model
  actually uses.
- **Product photos curated per category, not per SKU**: REES46 has no
  product photography at all, so `app/scripts/fetch_product_images.py`
  fetches a small, hand-picked pool per top-level category from Pexels
  rather than pretending to source 141,694 unique photos that don't
  exist. Stated explicitly here rather than left to look like a seamless
  per-product photo library.
- **Truncated vocabulary (top-N + `<OTHER>`)** instead of the full catalog:
  keeps the embedding table and output layer tractable for CPU-only training.
- **Sampled softmax as the training-time baseline**, not an upgrade path:
  given CPU-only training and ~15M training pairs against a ~40K-item
  vocabulary, a plain full softmax makes a single epoch take hours and a full
  run take days — sampled softmax (~100 negatives per step) is what makes
  iterating on this model practical at all on this hardware. Full logits are
  still computed exactly, just only at evaluation/serving time, never inside
  the training loop.
- **Prototype small, then scale**: every pipeline stage is first run and
  measured against a one-day slice (`notebooks/02_model_prototype.ipynb`)
  before running against the full 20M-row export — a pipeline bug found in
  minutes on a small slice is far cheaper than the same bug found hours into
  a full run.
- **Time-based split**, not random: prevents future-session leakage into
  training, which would silently inflate Recall@10/NDCG@10.
- **Popularity baseline reported alongside the model**: proves the model
  learned session-specific personalization rather than defaulting to
  "recommend whatever's popular."
- **Offline/online pipeline separation**: matches how production recommenders
  are actually structured — training is decoupled from serving latency.
- **MySQL as the storage layer**, bulk-loaded via `LOAD DATA INFILE` rather
  than row-by-row inserts: gives the project a real append-friendly system of
  record for new events, while keeping training reads on a fast Parquet
  export rather than repeated live queries against a 42M+ row table. At true
  production scale, high-volume clickstream data typically flows through an
  event stream into a data warehouse rather than a transactional RDBMS — an
  intentional, right-sized tradeoff for this project's scope, not an
  oversight.
- **Hybrid retrain strategy** (sliding-window full retrain + frequent
  warm-start fine-tune, Section 4) instead of either "retrain on all history
  forever" (unbounded cost growth) or "retrain on new data only" (catastrophic
  forgetting): the only version of "keep the model fresh" that stays
  computationally viable on CPU indefinitely, not just today.
- **Cold-start demo on a secondary catalog** (if applicable): stated
  explicitly rather than implied as a seamless integration.

---

## 12. Project Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 — Data & sequences | Download data, clean, build sessions, time-based split | ☑ (20M rows loaded + indexed in MySQL; `export.py`/`sessions.py`/`vocab.py`/`split.py` written; not yet run end-to-end against the full export) |
| 2 — Baseline model | GRU4Rec (sampled softmax) in Keras, popularity baseline, Recall@10/NDCG@10 | ☑ `src/model/*.py` built, trained (1M rows, test Recall@10=0.45 vs 0.09 baseline), live behind `/predict` — ☐ full 20M-row run for a higher ceiling |
| 3 — Serving | Storefront API + React UI (browse, search, cart) + `/predict` + "You might also like" | ☑ built & verified end-to-end (real data, no console/CORS errors) — running on a small-scale model pending a full retrain (Phase 2) |
| 4 — Cold-start (stretch) | CLIP embeddings, FAISS retrieval, API fallback path | ☐ |
| 5 — Polish | README, error handling, demo recording, deployment | ☐ |

---

## 13. Results

*(Held-out test set, 1M-row training run — `python -m src.model.train --limit 1000000`,
10/10 epochs, no early stop since val_recall@10 kept improving every
epoch. This is the model currently live behind `/predict`. The full
20M-row run would be expected to do better still — more training data
generally raises the ceiling — but hasn't been run yet; see Section 12.)*

| Model | Recall@10 | NDCG@10 | Coverage |
|---|---|---|---|
| Popularity baseline | 0.0855 | — | — |
| GRU4Rec | **0.4502** | **0.3291** | — |

GRU4Rec beats the popularity baseline by **5.3x** on Recall@10 — proof
it's learning genuine session-specific patterns, not just memorizing
what's generally popular (the whole point of Section 8's evaluation
design). Coverage not yet measured.

**CPU training time — measured, not just estimated.** The prototype notebook
was run end-to-end on a one-day slice (694,256 training pairs, 40,003-token
vocab, batch size 256, 8-thread CPU): 3 epochs took 595.8s / 508.9s / 439.8s,
with loss dropping 3.62 → 1.91 → 1.33 and Recall@10 = **0.3915** vs a
popularity-baseline Recall@10 of **0.0700** — a 5.6x improvement after just 3
epochs on one day of data, confirming the sampled-softmax approach is
actually learning, not just running.

Scaling the steady-state (~440-510s/epoch) by the ratio of training pairs
(694K sample vs. ~13-15M at full scale) gives a real estimate for the full
20M-row run: **roughly 2.5-3 hours/epoch**, ~1-1.3 days for 10 epochs (likely
less with early stopping) — noticeably better than the 1-6 hr/epoch,
1-3 day range a plain full-softmax model would need on the same hardware,
and the whole reason sampled softmax was made the training-time baseline
(Section 7) rather than a later optimization.
