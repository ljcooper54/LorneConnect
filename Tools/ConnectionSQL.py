# Copyright 2025 H2so4 Consulting LLC
# File: ConnectionSQL.py

"""
ConnectionSQL.py - lightweight phpMyAdmin-style SQLite browser/editor.

Features:
- Choose DB via --db PATH (default: App/constants.py DB_FILE, else ./connections.db)
- Schema browser (tables + columns + indexes)
- Per-table stats (row counts, columns)
- Table browse with pagination and inline editing (UPDATE by primary key)
- Basic SQL query runner (SELECT only by default; can enable writes with --allow-write-sql)
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, redirect, render_template_string, request, url_for
from markupsafe import Markup


def _default_db_path() -> str:
    # Compute default DB path from App/constants.py if available; else ./connections.db.
    try:
        from App.constants import DB_FILE  # type: ignore
        if DB_FILE:
            return os.path.abspath(DB_FILE)
    except Exception:
        pass
    return os.path.abspath("connections.db")
# _default_db_path


def _connect(db_path: str) -> sqlite3.Connection:
    # Create a SQLite connection with Row results.
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
# _connect


def _list_tables(conn: sqlite3.Connection) -> List[str]:
    # Return user tables (excluding sqlite internal tables).
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [r["name"] for r in cur.fetchall()]
# _list_tables


def _table_info(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    # Return PRAGMA table_info for the table.
    cur = conn.execute(f"PRAGMA table_info({table})")
    out: List[Dict[str, Any]] = []
    for r in cur.fetchall():
        out.append(
            {
                "cid": r["cid"],
                "name": r["name"],
                "type": r["type"],
                "notnull": r["notnull"],
                "dflt_value": r["dflt_value"],
                "pk": r["pk"],
            }
        )
    return out
# _table_info


def _primary_key_columns(table_info: List[Dict[str, Any]]) -> List[str]:
    # Extract primary key columns from PRAGMA table_info output.
    pk_cols = [c["name"] for c in table_info if int(c.get("pk") or 0) > 0]
    # SQLite pk order is by pk index; preserve order
    pk_cols_sorted = sorted(pk_cols, key=lambda n: next(int(c["pk"]) for c in table_info if c["name"] == n))
    return pk_cols_sorted
# _primary_key_columns


def _index_list(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    # Return PRAGMA index_list and index_info details.
    cur = conn.execute(f"PRAGMA index_list({table})")
    indexes = []
    for r in cur.fetchall():
        idx_name = r["name"]
        info = conn.execute(f"PRAGMA index_info({idx_name})").fetchall()
        cols = [x["name"] for x in info]
        indexes.append(
            {
                "name": idx_name,
                "unique": r["unique"],
                "origin": r["origin"],
                "partial": r["partial"],
                "columns": cols,
            }
        )
    return indexes
# _index_list


def create_app(db_path: str, allow_write_sql: bool = False) -> Flask:
    # Create and configure the Flask app.
    app = Flask(__name__)

    # Render a page by injecting a rendered body template into BASE_HTML. (Start)
    def _render_page(title: str, body_template: str, **context):
        # Render the body first (can use Jinja control structures), then inject into base.
        context = dict(context)
        context.setdefault("title", title)
        context.setdefault("db_path", app.config.get("DB_PATH", ""))

        body_html = render_template_string(body_template, **context)
        return render_template_string(BASE_HTML, body=Markup(body_html), **context)
    # end def _render_page  # _render_page

    app.config["DB_PATH"] = db_path
    app.config["ALLOW_WRITE_SQL"] = allow_write_sql

    BASE_HTML = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>ConnectionSQL - {{ title }}</title>
      <style>
        body { font-family: -apple-system, system-ui, Segoe UI, Roboto, Arial; margin: 16px; }
        .topbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
        .pill { padding: 4px 10px; border: 1px solid #ccc; border-radius: 999px; background: #f8f8f8; }
        a { text-decoration: none; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
        th { background: #f3f3f3; position: sticky; top: 0; }
        .grid { overflow: auto; max-height: 70vh; border: 1px solid #ddd; }
        .row-actions { white-space: nowrap; }
        input[type=text] { width: 100%; box-sizing: border-box; }
        textarea { width: 100%; height: 140px; box-sizing: border-box; font-family: ui-monospace, Menlo, Consolas, monospace; }
        .muted { color: #666; }
        .error { color: #b00020; }
        .ok { color: #0a7a0a; }
        .nav { display: flex; gap: 10px; margin: 10px 0; }
        .nav a { padding: 6px 10px; border: 1px solid #ddd; border-radius: 8px; }
      </style>
    </head>
    <body>
      <div class="topbar">
        <div class="pill"><b>DB:</b> {{ db_path }}</div>
        <div class="nav">
          <a href="{{ url_for('home') }}">Home</a>
          <a href="{{ url_for('schema') }}">Schema</a>
          <a href="{{ url_for('stats') }}">Stats</a>
          <a href="{{ url_for('sql') }}">SQL</a>
        </div>
      </div>
      {{ body|safe }}
    </body>
    </html>
    """

    @app.route("/")
    def home():
        # Render landing page with table list.
        conn = _connect(app.config["DB_PATH"])
        tables = _list_tables(conn)
        conn.close()
                return _render_page(
            'Home',
            """
            
              <h2>Tables</h2>
              <ul>
                {% for t in tables %}
                  <li><a href="{{ url_for('browse_table', table=t) }}">{{ t }}</a></li>
                {% endfor %}
              </ul>
              {% if not tables %}
                <p class="muted">No tables found.</p>
              {% endif %}
            """,
            ,
            db_path=app.config["DB_PATH"],
            tables=tables,
        )# end def home  # home

    @app.route("/schema")
    def schema():
        # Display schema: tables, columns, indexes.
        conn = _connect(app.config["DB_PATH"])
        tables = _list_tables(conn)
        schema_data = []
        for t in tables:
            ti = _table_info(conn, t)
            idx = _index_list(conn, t)
            schema_data.append({"table": t, "columns": ti, "indexes": idx})
        conn.close()

                return _render_page(
            'Schema',
            """
            
              <h2>Schema</h2>
              {% for item in schema_data %}
                <h3 id="{{ item.table }}">{{ item.table }}</h3>
                <p class="muted">
                  <a href="{{ url_for('browse_table', table=item.table) }}">Browse/Edit</a>
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>cid</th><th>name</th><th>type</th><th>notnull</th><th>default</th><th>pk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {% for c in item.columns %}
                      <tr>
                        <td>{{ c.cid }}</td>
                        <td><code>{{ c.name }}</code></td>
                        <td>{{ c.type }}</td>
                        <td>{{ c.notnull }}</td>
                        <td>{{ c.dflt_value }}</td>
                        <td>{{ c.pk }}</td>
                      </tr>
                    {% endfor %}
                  </tbody>
                </table>

                <h4>Indexes</h4>
                {% if item.indexes %}
                  <ul>
                    {% for i in item.indexes %}
                      <li>
                        <code>{{ i.name }}</code>
                        (unique={{ i.unique }}, origin={{ i.origin }}, partial={{ i.partial }})
                        — columns: {{ i.columns }}
                      </li>
                    {% endfor %}
                  </ul>
                {% else %}
                  <p class="muted">No indexes.</p>
                {% endif %}
                <hr>
              {% endfor %}
            """,
            ,
            db_path=app.config["DB_PATH"],
            schema_data=schema_data,
        )# end def schema  # schema

    @app.route("/stats")
    def stats():
        # Display per-table statistics (row counts, columns).
        conn = _connect(app.config["DB_PATH"])
        tables = _list_tables(conn)
        stats_rows = []
        for t in tables:
            try:
                row_count = conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            except Exception:
                row_count = "ERROR"
            cols = _table_info(conn, t)
            stats_rows.append({"table": t, "rows": row_count, "cols": len(cols)})
        conn.close()

                return _render_page(
            'Stats',
            """
            
              <h2>Stats</h2>
              <table>
                <thead><tr><th>Table</th><th>Rows</th><th>Columns</th><th>Action</th></tr></thead>
                <tbody>
                  {% for r in stats_rows %}
                    <tr>
                      <td><code>{{ r.table }}</code></td>
                      <td>{{ r.rows }}</td>
                      <td>{{ r.cols }}</td>
                      <td><a href="{{ url_for('browse_table', table=r.table) }}">Browse/Edit</a></td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
            """,
            ,
            db_path=app.config["DB_PATH"],
            stats_rows=stats_rows,
        )# end def stats  # stats

    @app.route("/table/<table>", methods=["GET", "POST"])
    def browse_table(table: str):
        # Browse/edit a table with pagination and inline updates.
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "50"))
        page = max(1, page)
        page_size = max(1, min(500, page_size))
        offset = (page - 1) * page_size

        msg = ""
        err = ""

        conn = _connect(app.config["DB_PATH"])
        ti = _table_info(conn, table)
        if not ti:
            conn.close()
            return redirect(url_for("home"))

        pk_cols = _primary_key_columns(ti)
        col_names = [c["name"] for c in ti]

        if request.method == "POST":
            try:
                # Expect hidden pk fields and editable fields in form.
                updates: Dict[str, Any] = {}
                pk_vals: Dict[str, Any] = {}

                for c in col_names:
                    form_key = f"col__{c}"
                    if form_key in request.form:
                        updates[c] = request.form.get(form_key)
                for pk in pk_cols:
                    pk_key = f"pk__{pk}"
                    pk_vals[pk] = request.form.get(pk_key)

                if not pk_cols:
                    raise RuntimeError("Cannot edit: table has no PRIMARY KEY.")

                # Do not update PK columns (keep them stable).
                for pk in pk_cols:
                    updates.pop(pk, None)

                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                where_clause = " AND ".join([f"{k} = ?" for k in pk_cols])
                params = list(updates.values()) + [pk_vals[k] for k in pk_cols]

                if not set_clause:
                    raise RuntimeError("No editable columns submitted.")

                conn.execute(f"UPDATE {table} SET {set_clause} WHERE {where_clause}", params)
                conn.commit()
                msg = "Row updated."
            except Exception as e:
                err = f"{e}"

        # Fetch total + page rows
        total = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        cur = conn.execute(f"SELECT * FROM {table} LIMIT ? OFFSET ?", (page_size, offset))
        rows = cur.fetchall()
        conn.close()

                return _render_page(
            'Page',
            """
            
              <h2>Browse/Edit: <code>{{ table }}</code></h2>
              <p class="muted">
                Rows: {{ total }} • Page {{ page }} • Page size {{ page_size }}
              </p>

              {% if msg %}<p class="ok">{{ msg }}</p>{% endif %}
              {% if err %}<p class="error">{{ err }}</p>{% endif %}

              {% if not pk_cols %}
                <p class="error">
                  This table has no PRIMARY KEY. Editing is disabled because updates would be ambiguous.
                </p>
              {% endif %}

              <div class="grid">
                <table>
                  <thead>
                    <tr>
                      <th>Action</th>
                      {% for c in col_names %}
                        <th><code>{{ c }}</code></th>
                      {% endfor %}
                    </tr>
                  </thead>
                  <tbody>
                    {% for row in rows %}
                      <tr>
                        <td class="row-actions">
                          {% if pk_cols %}
                          <form method="post" style="margin:0;">
                            {% for pk in pk_cols %}
                              <input type="hidden" name="pk__{{ pk }}" value="{{ row[pk] }}">
                            {% endfor %}
                            {% for c in col_names %}
                              <input type="hidden" name="col__{{ c }}" value="{{ row[c] }}">
                            {% endfor %}
                            <button type="submit">Edit</button>
                          </form>
                          {% else %}
                            <span class="muted">N/A</span>
                          {% endif %}
                        </td>
                        {% for c in col_names %}
                          <td>{{ row[c] }}</td>
                        {% endfor %}
                      </tr>
                    {% endfor %}
                  </tbody>
                </table>
              </div>

              <h3>Inline Edit (selected row)</h3>
              <p class="muted">Click “Edit” on a row to load its current values into the form below.</p>

              {% if pk_cols %}
                <form method="post">
                  <table>
                    <thead><tr><th>Column</th><th>Value</th></tr></thead>
                    <tbody>
                      {% for c in col_names %}
                        <tr>
                          <td><code>{{ c }}</code>{% if c in pk_cols %} <span class="muted">(PK)</span>{% endif %}</td>
                          <td>
                            <input type="text" name="col__{{ c }}" value="{{ request.form.get('col__'+c, '') }}">
                            {% if c in pk_cols %}
                              <input type="hidden" name="pk__{{ c }}" value="{{ request.form.get('pk__'+c, '') }}">
                            {% endif %}
                          </td>
                        </tr>
                      {% endfor %}
                    </tbody>
                  </table>
                  <button type="submit">Save Update</button>
                </form>
              {% endif %}

              <div class="nav">
                {% if page > 1 %}
                  <a href="{{ url_for('browse_table', table=table, page=page-1, page_size=page_size) }}">Prev</a>
                {% endif %}
                {% if (page * page_size) < total %}
                  <a href="{{ url_for('browse_table', table=table, page=page+1, page_size=page_size) }}">Next</a>
                {% endif %}
              </div>
            """,
            title=f"Table {table}",
            db_path=app.config["DB_PATH"],
            table=table,
            total=total,
            page=page,
            page_size=page_size,
            rows=rows,
            col_names=col_names,
            pk_cols=pk_cols,
            msg=msg,
            err=err,
            request=request,
        )# end def browse_table  # browse_table

    @app.route("/sql", methods=["GET", "POST"])
    def sql():
        # Run ad-hoc SQL (SELECT only by default).
        q = ""
        result_rows: List[sqlite3.Row] = []
        cols: List[str] = []
        msg = ""
        err = ""

        if request.method == "POST":
            q = (request.form.get("q") or "").strip()
            if q:
                try:
                    lowered = q.lstrip().lower()
                    if not app.config["ALLOW_WRITE_SQL"]:
                        if not lowered.startswith("select") and not lowered.startswith("pragma"):
                            raise RuntimeError("Write SQL disabled. Use --allow-write-sql to enable.")
                    conn = _connect(app.config["DB_PATH"])
                    cur = conn.execute(q)
                    if cur.description:
                        cols = [d[0] for d in cur.description]
                        result_rows = cur.fetchall()
                    else:
                        conn.commit()
                        msg = "Statement executed."
                    conn.close()
                except Exception as e:
                    err = f"{e}"

                return _render_page(
            'SQL',
            """
            
              <h2>SQL</h2>
              <p class="muted">
                {% if allow_write %}
                  Write SQL enabled.
                {% else %}
                  SELECT/PRAGMA only (run with <code>--allow-write-sql</code> to enable writes).
                {% endif %}
              </p>

              {% if msg %}<p class="ok">{{ msg }}</p>{% endif %}
              {% if err %}<p class="error">{{ err }}</p>{% endif %}

              <form method="post">
                <textarea name="q" placeholder="SELECT * FROM words LIMIT 50;">{{ q }}</textarea><br>
                <button type="submit">Run</button>
              </form>

              {% if cols %}
                <h3>Results</h3>
                <div class="grid">
                  <table>
                    <thead>
                      <tr>
                        {% for c in cols %}<th><code>{{ c }}</code></th>{% endfor %}
                      </tr>
                    </thead>
                    <tbody>
                      {% for r in result_rows %}
                        <tr>
                          {% for c in cols %}
                            <td>{{ r[c] }}</td>
                          {% endfor %}
                        </tr>
                      {% endfor %}
                    </tbody>
                  </table>
                </div>
              {% endif %}
            """,
            ,
            db_path=app.config["DB_PATH"],
            q=q,
            cols=cols,
            result_rows=result_rows,
            msg=msg,
            err=err,
            allow_write=app.config["ALLOW_WRITE_SQL"],
        )# end def sql  # sql

    return app
# create_app


def main() -> None:
    # Parse args and run the ConnectionSQL Flask server.
    parser = argparse.ArgumentParser(description="ConnectionSQL - SQLite browser/editor")
    parser.add_argument("--db", default=_default_db_path(), help="Path to SQLite DB file")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5050, help="Bind port (default 5050)")
    parser.add_argument("--allow-write-sql", action="store_true", help="Allow non-SELECT SQL in SQL tab")
    args = parser.parse_args()

    app = create_app(db_path=os.path.abspath(args.db), allow_write_sql=bool(args.allow_write_sql))
    app.run(host=args.host, port=args.port, debug=False)
# main


if __name__ == "__main__":
    main()
