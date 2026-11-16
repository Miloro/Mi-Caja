# -*- coding: utf-8 -*-
"""
Sistema de venta con lector de codigo de barras.
- Agregar/editar productos (codigo, nombre, descripcion, precio, stock)
- Productos UNITARIOS (por unidad) o PESABLES (precio por X gramos)
- Pantalla de venta: escanear, sumar en vivo, cerrar venta
- Descuenta el stock al cerrar la venta
- Todo local, sin internet. Los datos quedan en 'datos.db'.
"""

import os
import sqlite3
import threading
import webbrowser
from datetime import date, datetime

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "datos.db")

app = Flask(__name__)
# Evitar que el navegador muestre versiones viejas (cache) de las pantallas/estilos
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _columnas(con, tabla):
    return {row["name"] for row in con.execute(f"PRAGMA table_info({tabla})")}


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo        TEXT    UNIQUE NOT NULL,
            nombre        TEXT    NOT NULL,
            descripcion   TEXT    NOT NULL DEFAULT '',
            tipo          TEXT    NOT NULL DEFAULT 'unitario',  -- 'unitario' | 'pesable'
            precio        REAL    NOT NULL DEFAULT 0,
            unidad_gramos REAL    NOT NULL DEFAULT 0,           -- para pesables: base en gramos
            stock         REAL    NOT NULL DEFAULT 0            -- unidades o gramos segun tipo
        );

        CREATE TABLE IF NOT EXISTS ventas (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha  TEXT    NOT NULL,
            total  REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS venta_items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id      INTEGER NOT NULL,
            producto_id   INTEGER,
            codigo        TEXT,
            nombre        TEXT,
            tipo          TEXT    DEFAULT 'unitario',
            precio        REAL,
            unidad_gramos REAL    DEFAULT 0,
            cantidad      REAL,
            subtotal      REAL,
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lotes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id   INTEGER NOT NULL,
            codigo_lote   TEXT    NOT NULL DEFAULT '',
            vencimiento   TEXT    NOT NULL DEFAULT '',   -- 'YYYY-MM-DD' o vacio
            cantidad      REAL    NOT NULL DEFAULT 0,
            fecha_ingreso TEXT,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
        );
        """
    )

    # --- Migracion: agregar columnas nuevas a bases ya existentes ---
    cols = _columnas(con, "productos")
    if "descripcion" not in cols:
        con.execute("ALTER TABLE productos ADD COLUMN descripcion TEXT NOT NULL DEFAULT ''")
    if "tipo" not in cols:
        con.execute("ALTER TABLE productos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'unitario'")
    if "unidad_gramos" not in cols:
        con.execute("ALTER TABLE productos ADD COLUMN unidad_gramos REAL NOT NULL DEFAULT 0")

    cols_items = _columnas(con, "venta_items")
    if "tipo" not in cols_items:
        con.execute("ALTER TABLE venta_items ADD COLUMN tipo TEXT DEFAULT 'unitario'")
    if "unidad_gramos" not in cols_items:
        con.execute("ALTER TABLE venta_items ADD COLUMN unidad_gramos REAL DEFAULT 0")

    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Pantallas
# ---------------------------------------------------------------------------
@app.route("/")
def venta():
    return render_template("venta.html")


@app.route("/productos")
def productos():
    db = get_db()
    busqueda = (request.args.get("q") or "").strip()
    if busqueda:
        like = f"%{busqueda}%"
        filas = db.execute(
            "SELECT * FROM productos WHERE codigo LIKE ? OR nombre LIKE ? OR descripcion LIKE ? "
            "ORDER BY nombre COLLATE NOCASE",
            (like, like, like),
        ).fetchall()
    else:
        filas = db.execute(
            "SELECT * FROM productos ORDER BY nombre COLLATE NOCASE"
        ).fetchall()

    # Lotes por producto (para la columna de vencimiento y el desplegable)
    lotes_por_producto = {}
    venc_por_producto = {}
    for row in db.execute("SELECT * FROM lotes ORDER BY vencimiento = '' , vencimiento ASC"):
        lote = dict(row)
        lote.update(_estado_venc(lote["vencimiento"]))
        lotes_por_producto.setdefault(lote["producto_id"], []).append(lote)
        # Guardar el vencimiento mas proximo (no vacio) por producto
        if lote["vencimiento"]:
            actual = venc_por_producto.get(lote["producto_id"])
            if actual is None or lote["vencimiento"] < actual["vencimiento"]:
                venc_por_producto[lote["producto_id"]] = lote

    return render_template(
        "productos.html",
        productos=filas,
        busqueda=busqueda,
        lotes_por_producto=lotes_por_producto,
        venc_por_producto=venc_por_producto,
    )


@app.route("/productos/ingreso", methods=["POST"])
def ingreso_stock():
    """Ingreso de mercaderia: suma stock y (opcional) registra un lote con vencimiento."""
    db = get_db()
    codigo = (request.form.get("codigo") or "").strip()
    cantidad = _a_numero(request.form.get("cantidad"))
    codigo_lote = (request.form.get("codigo_lote") or "").strip()
    vencimiento = _normalizar_fecha(request.form.get("vencimiento"))

    prod = db.execute("SELECT * FROM productos WHERE codigo = ?", (codigo,)).fetchone()
    if prod is None or cantidad <= 0:
        return redirect(url_for("productos"))

    db.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, prod["id"]))
    if codigo_lote or vencimiento:
        db.execute(
            "INSERT INTO lotes (producto_id, codigo_lote, vencimiento, cantidad, fecha_ingreso) "
            "VALUES (?, ?, ?, ?, ?)",
            (prod["id"], codigo_lote, vencimiento, cantidad,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    db.commit()
    return redirect(url_for("productos"))


@app.route("/lotes")
def lotes():
    db = get_db()
    filas = db.execute(
        "SELECT l.*, p.nombre AS producto_nombre, p.codigo AS producto_codigo "
        "FROM lotes l JOIN productos p ON p.id = l.producto_id "
        "ORDER BY l.vencimiento = '' , l.vencimiento ASC"
    ).fetchall()
    items = []
    for row in filas:
        d = dict(row)
        d.update(_estado_venc(d["vencimiento"]))
        items.append(d)
    return render_template("lotes.html", lotes=items)


@app.route("/lotes/<int:lid>/borrar", methods=["POST"])
def borrar_lote(lid):
    db = get_db()
    db.execute("DELETE FROM lotes WHERE id = ?", (lid,))
    db.commit()
    return redirect(url_for("lotes"))


@app.route("/codigos")
def codigos():
    return render_template("codigos.html")


@app.route("/eoq")
def eoq():
    db = get_db()
    productos_lista = db.execute(
        "SELECT codigo, nombre, precio FROM productos ORDER BY nombre COLLATE NOCASE"
    ).fetchall()
    return render_template("eoq.html", productos=productos_lista)


@app.route("/productos", methods=["POST"])
def crear_producto():
    db = get_db()
    datos = _leer_form(request.form)
    if not datos["codigo"] or not datos["nombre"]:
        return redirect(url_for("productos"))
    try:
        db.execute(
            "INSERT INTO productos (codigo, nombre, descripcion, tipo, precio, unidad_gramos, stock) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datos["codigo"], datos["nombre"], datos["descripcion"], datos["tipo"],
             datos["precio"], datos["unidad_gramos"], datos["stock"]),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # Ya existe ese codigo: actualizamos datos y SUMAMOS stock
        db.execute(
            "UPDATE productos SET nombre=?, descripcion=?, tipo=?, precio=?, unidad_gramos=?, "
            "stock = stock + ? WHERE codigo=?",
            (datos["nombre"], datos["descripcion"], datos["tipo"], datos["precio"],
             datos["unidad_gramos"], datos["stock"], datos["codigo"]),
        )
        db.commit()
    return redirect(url_for("productos"))


@app.route("/productos/<int:pid>/editar", methods=["POST"])
def editar_producto(pid):
    db = get_db()
    datos = _leer_form(request.form)
    if datos["codigo"] and datos["nombre"]:
        db.execute(
            "UPDATE productos SET codigo=?, nombre=?, descripcion=?, tipo=?, precio=?, "
            "unidad_gramos=?, stock=? WHERE id=?",
            (datos["codigo"], datos["nombre"], datos["descripcion"], datos["tipo"],
             datos["precio"], datos["unidad_gramos"], datos["stock"], pid),
        )
        db.commit()
    return redirect(url_for("productos"))


@app.route("/productos/<int:pid>/borrar", methods=["POST"])
def borrar_producto(pid):
    db = get_db()
    db.execute("DELETE FROM productos WHERE id = ?", (pid,))
    db.commit()
    return redirect(url_for("productos"))


@app.route("/ventas")
def historial():
    db = get_db()
    ventas = db.execute(
        "SELECT * FROM ventas ORDER BY id DESC LIMIT 200"
    ).fetchall()
    items_por_venta = {}
    for v in ventas:
        items_por_venta[v["id"]] = db.execute(
            "SELECT * FROM venta_items WHERE venta_id = ?", (v["id"],)
        ).fetchall()
    return render_template(
        "ventas.html", ventas=ventas, items_por_venta=items_por_venta
    )


# ---------------------------------------------------------------------------
# API (usada por la pantalla de venta)
# ---------------------------------------------------------------------------
def _json_producto(fila):
    return {
        "encontrado": True,
        "id": fila["id"],
        "codigo": fila["codigo"],
        "nombre": fila["nombre"],
        "descripcion": fila["descripcion"],
        "tipo": fila["tipo"],
        "precio": fila["precio"],
        "unidad_gramos": fila["unidad_gramos"],
        "stock": fila["stock"],
    }


@app.route("/api/producto/<codigo>")
def api_producto(codigo):
    db = get_db()
    fila = db.execute(
        "SELECT * FROM productos WHERE codigo = ?", (codigo.strip(),)
    ).fetchone()
    if fila is None:
        return jsonify({"encontrado": False}), 404
    return jsonify(_json_producto(fila))


@app.route("/api/producto-rapido", methods=["POST"])
def api_producto_rapido():
    """Alta rapida de un producto desde la pantalla de venta."""
    db = get_db()
    datos = _leer_form(request.get_json(force=True, silent=True) or {})
    if not datos["codigo"] or not datos["nombre"]:
        return jsonify({"ok": False, "error": "Faltan datos"}), 400
    try:
        cur = db.execute(
            "INSERT INTO productos (codigo, nombre, descripcion, tipo, precio, unidad_gramos, stock) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datos["codigo"], datos["nombre"], datos["descripcion"], datos["tipo"],
             datos["precio"], datos["unidad_gramos"], datos["stock"]),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "El codigo ya existe"}), 409
    fila = db.execute("SELECT * FROM productos WHERE id = ?", (cur.lastrowid,)).fetchone()
    res = _json_producto(fila)
    res["ok"] = True
    return jsonify(res)


@app.route("/api/venta", methods=["POST"])
def api_cerrar_venta():
    """Cierra la venta: registra y descuenta el stock."""
    db = get_db()
    datos = request.get_json(force=True, silent=True) or {}
    items = datos.get("items") or []
    if not items:
        return jsonify({"ok": False, "error": "La venta esta vacia"}), 400

    total = 0.0
    detalle = []
    for item in items:
        codigo = (item.get("codigo") or "").strip()
        cantidad = _a_numero(item.get("cantidad"))
        if cantidad <= 0:
            continue
        prod = db.execute(
            "SELECT * FROM productos WHERE codigo = ?", (codigo,)
        ).fetchone()
        if prod is None:
            # Producto borrado: usamos los datos que vinieron del carrito
            tipo = item.get("tipo") or "unitario"
            precio = _a_numero(item.get("precio"))
            unidad_gramos = _a_numero(item.get("unidad_gramos"))
            nombre = item.get("nombre") or codigo
            subtotal = _subtotal(tipo, precio, unidad_gramos, cantidad)
            detalle.append(dict(producto_id=None, codigo=codigo, nombre=nombre, tipo=tipo,
                                precio=precio, unidad_gramos=unidad_gramos,
                                cantidad=cantidad, subtotal=subtotal))
            total += subtotal
            continue

        subtotal = _subtotal(prod["tipo"], prod["precio"], prod["unidad_gramos"], cantidad)
        total += subtotal
        detalle.append(dict(producto_id=prod["id"], codigo=prod["codigo"], nombre=prod["nombre"],
                            tipo=prod["tipo"], precio=prod["precio"],
                            unidad_gramos=prod["unidad_gramos"], cantidad=cantidad,
                            subtotal=subtotal))
        # Descontar stock (en unidades o en gramos, segun el tipo)
        db.execute("UPDATE productos SET stock = stock - ? WHERE id = ?",
                   (cantidad, prod["id"]))

    if not detalle:
        return jsonify({"ok": False, "error": "La venta esta vacia"}), 400

    total = round(total, 2)
    cur = db.execute(
        "INSERT INTO ventas (fecha, total) VALUES (?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total),
    )
    venta_id = cur.lastrowid
    for d in detalle:
        db.execute(
            "INSERT INTO venta_items "
            "(venta_id, producto_id, codigo, nombre, tipo, precio, unidad_gramos, cantidad, subtotal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (venta_id, d["producto_id"], d["codigo"], d["nombre"], d["tipo"],
             d["precio"], d["unidad_gramos"], d["cantidad"], d["subtotal"]),
        )
    db.commit()
    return jsonify({"ok": True, "venta_id": venta_id, "total": total})


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _leer_form(form):
    tipo = "pesable" if (form.get("tipo") or "").strip() == "pesable" else "unitario"
    unidad_gramos = _a_numero(form.get("unidad_gramos"))
    if tipo == "pesable":
        if unidad_gramos <= 0:
            unidad_gramos = 100.0  # base por defecto: 100 g
    else:
        unidad_gramos = 0.0
    return {
        "codigo": (form.get("codigo") or "").strip(),
        "nombre": (form.get("nombre") or "").strip(),
        "descripcion": (form.get("descripcion") or "").strip(),
        "tipo": tipo,
        "precio": _a_numero(form.get("precio")),
        "unidad_gramos": unidad_gramos,
        "stock": _a_numero(form.get("stock")),
    }


def _subtotal(tipo, precio, unidad_gramos, cantidad):
    if tipo == "pesable":
        base = unidad_gramos if unidad_gramos and unidad_gramos > 0 else 1.0
        return round(precio * cantidad / base, 2)
    return round(precio * cantidad, 2)


def _a_numero(valor):
    try:
        return round(float(str(valor).replace(",", ".")), 3)
    except (TypeError, ValueError):
        return 0.0


def _normalizar_fecha(valor):
    """Devuelve 'YYYY-MM-DD' si es una fecha valida, si no cadena vacia."""
    valor = (str(valor or "")).strip()
    if not valor:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


# Dias desde los cuales se avisa "por vencer"
DIAS_AVISO_VENCIMIENTO = 30


def _estado_venc(venc):
    """Clasifica un vencimiento: vencido / pronto / ok. Devuelve dict para el template."""
    venc = (venc or "").strip()
    if not venc:
        return {"estado": "", "dias": None, "venc_texto": "—"}
    try:
        f = datetime.strptime(venc, "%Y-%m-%d").date()
    except ValueError:
        return {"estado": "", "dias": None, "venc_texto": venc}
    dias = (f - date.today()).days
    if dias < 0:
        estado = "vencido"
    elif dias <= DIAS_AVISO_VENCIMIENTO:
        estado = "pronto"
    else:
        estado = "ok"
    return {"estado": estado, "dias": dias, "venc_texto": f.strftime("%d/%m/%Y")}


def _abrir_navegador():
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    init_db()
    threading.Timer(1.2, _abrir_navegador).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
