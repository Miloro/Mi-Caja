# Mi Caja

**🌐 Idioma / Language:** [🇪🇸 Español](#-español) · [🇬🇧 English](#-english)

---

## 🇪🇸 Español

Sistema de punto de venta (POS) simple, en español y fácil de usar, pensado para negocios chicos. Funciona **100% local y sin internet**: tus datos nunca salen de tu computadora.

### Qué hace
- **Venta con lector de código de barras**: escaneás, el total se suma solo y al cerrar la venta se descuenta el stock.
- **Productos** por unidad o **pesables** (precio por X gramos): alta, edición y borrado.
- **Stock y lotes** con control de **vencimientos** (avisa lo que está por vencer).
- **Historial de ventas**.

### Requisitos
- Windows con [Python](https://www.python.org/) instalado.
- Un lector de código de barras (opcional: funciona como un teclado, no requiere instalación).

### Cómo usarlo
1. Hacé doble clic en **`iniciar.bat`**. La primera vez instala lo necesario (tarda un momento) y se abre solo en `http://localhost:5000`.
2. Para cerrar el sistema, cerrá la ventana negra.

### Tus datos
Todo se guarda en **`datos.db`** (en esta carpeta). Para un **backup**, copiá ese archivo a un pendrive; para restaurar, volvé a pegarlo acá. *(No se incluye en el repositorio: contiene los datos de cada negocio.)*

### Tecnología
Python + [Flask](https://flask.palletsprojects.com/) · Base de datos SQLite (archivo local).

### Licencia
[MIT](LICENSE) — uso libre.

---

## 🇬🇧 English

A simple, easy-to-use point-of-sale (POS) system, designed for small businesses. Runs **100% locally, no internet needed**: your data never leaves your computer.

### Features
- **Barcode-scanner sales**: scan an item, the total adds up automatically, and stock is deducted when you close the sale.
- **Products** by unit or **by weight** (price per X grams): add, edit and delete.
- **Stock and batches** with **expiration-date** tracking (warns about items about to expire).
- **Sales history**.

### Requirements
- Windows with [Python](https://www.python.org/) installed.
- A barcode scanner (optional: it works like a keyboard, no setup needed).

### How to use
1. Double-click **`iniciar.bat`**. The first run installs everything needed (takes a moment) and opens automatically at `http://localhost:5000`.
2. To close the system, close the black window.

### Your data
Everything is stored in **`datos.db`** (in this folder). To **back up**, copy that file to a USB drive; to restore, paste it back here. *(It is not included in the repository, since it holds each business's data.)*

### Tech
Python + [Flask](https://flask.palletsprojects.com/) · SQLite database (local file).

### License
[MIT](LICENSE) — free to use.
