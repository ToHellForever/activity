import sqlite3

conn = sqlite3.connect("db.sqlite3")
cur = conn.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("consent-like tables:", [t for t in tables if "consent" in t])
for t in [t for t in tables if "consent" in t]:
    print("----", t)
    print(cur.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0])
    print("rows:", cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0])
