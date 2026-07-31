"""
Generate the example files used to smoke-test the data-analytics-agents toolkit:

  examples/ventas_sample.csv   ~120 rows, with intentional nulls/dupes/mixed types
  examples/notes_example.sqlite 3 tables: customers, products, orders
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# 1. ventas_sample.csv
# ---------------------------------------------------------------------------

def build_ventas_csv() -> Path:
    n = 120
    start = date(2024, 1, 1)
    days = [start + timedelta(days=int(d)) for d in RNG.integers(0, 120, size=n)]

    categorias = ["Electronics", "Home", "Apparel", "Books", "Toys"]
    canales = ["web", "tienda", "marketplace"]

    df = pd.DataFrame({
        "order_id": range(1001, 1001 + n),
        "order_date": days,
        "categoria": RNG.choice(categorias, size=n),
        "canal": RNG.choice(canales, size=n),
        "units": RNG.integers(1, 8, size=n),
        "unit_price": np.round(RNG.uniform(5.0, 250.0, size=n), 2),
    })
    df["revenue"] = (df["units"] * df["unit_price"]).round(2)

    # Inject realism problems so the profiler has something to find:
    # 1. ~5% null in revenue (mimic bad join)
    nulls_idx = RNG.choice(df.index, size=6, replace=False)
    df.loc[nulls_idx, "revenue"] = np.nan

    # 2. string-style null tokens in categoria and canal
    str_null_idx = RNG.choice(df.index, size=4, replace=False)
    for i in str_null_idx[:2]:
        df.loc[i, "categoria"] = "nan"  # string-style null
    for i in str_null_idx[2:]:
        df.loc[i, "canal"] = "NULL"

    # 3. mixed dtype in canal: numeric-looking value
    df.loc[RNG.choice(df.index), "canal"] = "  web  "

    # 4. a couple of duplicate rows
    dup_idx = RNG.choice(df.index, size=3, replace=False)
    df = pd.concat([df, df.loc[dup_idx]], ignore_index=True)

    # 5. one whitespace-padded categoria
    df.loc[df.index[0], "categoria"] = "  Electronics  "

    out = EXAMPLES_DIR / "ventas_sample.csv"
    df.to_csv(out, index=False)
    return out


# ---------------------------------------------------------------------------
# 2. notes_example.sqlite
# ---------------------------------------------------------------------------

def build_sqlite() -> Path:
    out = EXAMPLES_DIR / "notes_example.sqlite"
    if out.exists():
        out.unlink()

    conn = sqlite3.connect(out)
    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS customers;

    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        segment     TEXT NOT NULL,    -- SMB / Mid-market / Enterprise
        country     TEXT NOT NULL,
        signup_date TEXT NOT NULL     -- ISO date
    );

    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        sku        TEXT NOT NULL UNIQUE,
        category   TEXT NOT NULL,
        list_price REAL NOT NULL
    );

    CREATE TABLE orders (
        order_id    INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
        product_id  INTEGER NOT NULL REFERENCES products(product_id),
        order_date  TEXT NOT NULL,    -- ISO date
        units       INTEGER NOT NULL,
        discount    REAL NOT NULL     -- 0.0 .. 0.4
    );
    """)

    # Seed customers
    segments = ["SMB", "Mid-market", "Enterprise"]
    countries = ["CL", "AR", "PE", "MX", "US", "BR"]
    n_customers = 30
    customer_ids = list(range(1, n_customers + 1))
    cur.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [
            (cid,
             f"Customer {cid}",
             RNG.choice(segments),
             RNG.choice(countries),
             (date(2023, 1, 1) + timedelta(days=int(RNG.integers(0, 365)))).isoformat())
            for cid in customer_ids
        ],
    )

    # Seed products
    categories = ["Electronics", "Home", "Apparel", "Books", "Toys"]
    n_products = 25
    cur.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?)",
        [
            (pid,
             f"SKU-{1000 + pid}",
             RNG.choice(categories),
             float(round(RNG.uniform(5.0, 250.0), 2)))
            for pid in range(1, n_products + 1)
        ],
    )

    # Seed orders
    n_orders = 200
    cur.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
        [
            (oid,
             int(RNG.choice(customer_ids)),
             int(RNG.choice(list(range(1, n_products + 1)))),
             (date(2024, 1, 1) + timedelta(days=int(RNG.integers(0, 120)))).isoformat(),
             int(RNG.integers(1, 8)),
             float(round(RNG.uniform(0.0, 0.4), 2)))
            for oid in range(1, n_orders + 1)
        ],
    )

    conn.commit()
    conn.close()
    return out


def main() -> None:
    csv_path = build_ventas_csv()
    db_path = build_sqlite()
    print(f"wrote {csv_path} ({(csv_path.stat().st_size / 1024):.1f} KB)")
    print(f"wrote {db_path} ({(db_path.stat().st_size / 1024):.1f} KB)")


if __name__ == "__main__":
    main()
