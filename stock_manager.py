import csv
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

DATE_FMT = "%Y-%m-%d"
DB_FILE = Path("stock_manager.db")


class StockManagerDB:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    serial_number TEXT UNIQUE NOT NULL,
                    product TEXT NOT NULL,
                    entry_stock INTEGER NOT NULL CHECK(entry_stock >= 0),
                    available_stock INTEGER NOT NULL CHECK(available_stock >= 0),
                    cost REAL NOT NULL CHECK(cost >= 0),
                    sell REAL NOT NULL CHECK(sell >= 0),
                    date TEXT NOT NULL,
                    vendor TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_date TEXT NOT NULL,
                    serial_number TEXT NOT NULL,
                    product TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    unit_sell REAL NOT NULL CHECK(unit_sell >= 0),
                    total REAL NOT NULL CHECK(total >= 0),
                    customer_note TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (serial_number) REFERENCES products(serial_number)
                )
                """
            )

    def close(self):
        self.conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat(timespec="seconds")

    def add_product(self, payload: dict):
        now = self._now()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO products (
                    serial_number, product, entry_stock, available_stock,
                    cost, sell, date, vendor, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["serial_number"],
                    payload["product"],
                    payload["entry_stock"],
                    payload["entry_stock"],
                    payload["cost"],
                    payload["sell"],
                    payload["date"],
                    payload["vendor"],
                    payload["note"],
                    now,
                    now,
                ),
            )

    def update_product(self, product_id: int, payload: dict):
        with closing(self.conn.cursor()) as cur:
            cur.execute("SELECT entry_stock, available_stock FROM products WHERE id = ?", (product_id,))
            current = cur.fetchone()
            if not current:
                raise ValueError("Product not found")

            stock_delta = payload["entry_stock"] - current["entry_stock"]
            new_available = current["available_stock"] + stock_delta
            if new_available < 0:
                raise ValueError("Entry stock is lower than already sold quantity.")

            with self.conn:
                self.conn.execute(
                    """
                    UPDATE products
                    SET serial_number = ?, product = ?, entry_stock = ?, available_stock = ?,
                        cost = ?, sell = ?, date = ?, vendor = ?, note = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload["serial_number"],
                        payload["product"],
                        payload["entry_stock"],
                        new_available,
                        payload["cost"],
                        payload["sell"],
                        payload["date"],
                        payload["vendor"],
                        payload["note"],
                        self._now(),
                        product_id,
                    ),
                )

    def delete_product(self, product_id: int):
        with self.conn:
            self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def list_products(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT id, serial_number, product, entry_stock, available_stock,
                       cost, sell, date, vendor, note
                FROM products
                ORDER BY id DESC
                """
            )
            return cur.fetchall()

    def sell_item(self, serial_number: str, quantity: int, sale_date: str, customer_note: str = ""):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                "SELECT product, available_stock, sell FROM products WHERE serial_number = ?",
                (serial_number,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Serial number not found.")
            if quantity > row["available_stock"]:
                raise ValueError("Not enough available stock.")

            unit_sell = float(row["sell"])
            total = unit_sell * quantity
            now = self._now()
            with self.conn:
                self.conn.execute(
                    "UPDATE products SET available_stock = available_stock - ?, updated_at = ? WHERE serial_number = ?",
                    (quantity, now, serial_number),
                )
                self.conn.execute(
                    """
                    INSERT INTO sales (
                        sale_date, serial_number, product, quantity,
                        unit_sell, total, customer_note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sale_date, serial_number, row["product"], quantity, unit_sell, total, customer_note, now),
                )

    def list_sales(self):
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                """
                SELECT id, sale_date, serial_number, product, quantity, unit_sell, total, customer_note
                FROM sales
                ORDER BY id DESC
                """
            )
            return cur.fetchall()

    def export_backup(self, path: Path):
        products = [dict(row) for row in self.list_products()]
        sales = [dict(row) for row in self.list_sales()]
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"products": products, "sales": sales}, f, ensure_ascii=False, indent=2)

    def import_backup(self, path: Path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        products = data.get("products", [])
        sales = data.get("sales", [])

        with self.conn:
            self.conn.execute("DELETE FROM sales")
            self.conn.execute("DELETE FROM products")

            for p in products:
                now = self._now()
                self.conn.execute(
                    """
                    INSERT INTO products (
                        id, serial_number, product, entry_stock, available_stock,
                        cost, sell, date, vendor, note, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p.get("id"),
                        p["serial_number"],
                        p["product"],
                        int(p["entry_stock"]),
                        int(p["available_stock"]),
                        float(p["cost"]),
                        float(p["sell"]),
                        p["date"],
                        p.get("vendor", ""),
                        p.get("note", ""),
                        now,
                        now,
                    ),
                )

            for s in sales:
                now = self._now()
                self.conn.execute(
                    """
                    INSERT INTO sales (
                        id, sale_date, serial_number, product, quantity,
                        unit_sell, total, customer_note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s.get("id"),
                        s["sale_date"],
                        s["serial_number"],
                        s["product"],
                        int(s["quantity"]),
                        float(s["unit_sell"]),
                        float(s["total"]),
                        s.get("customer_note", ""),
                        now,
                    ),
                )


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Enterprise Stock Management")
        self.geometry("1400x780")
        self.minsize(1200, 700)

        self.db = StockManagerDB(DB_FILE)
        self.product_fields: dict[str, tk.Entry] = {}
        self.selected_product_id = None

        self._build_ui()
        self.refresh_products()
        self.refresh_sales()

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        stock_tab = ttk.Frame(nb)
        sales_tab = ttk.Frame(nb)
        backup_tab = ttk.Frame(nb)
        nb.add(stock_tab, text="Stock Management")
        nb.add(sales_tab, text="Selling Items")
        nb.add(backup_tab, text="Backup")

        self._build_stock_tab(stock_tab)
        self._build_sales_tab(sales_tab)
        self._build_backup_tab(backup_tab)

    def _build_stock_tab(self, parent):
        form = ttk.LabelFrame(parent, text="Product Entry")
        form.pack(fill="x", padx=8, pady=8)

        labels = [
            "serial_number",
            "product",
            "entry_stock",
            "cost",
            "sell",
            "date (YYYY-MM-DD)",
            "vendor",
            "note",
        ]

        for i, lbl in enumerate(labels):
            ttk.Label(form, text=lbl.replace("_", " ").title()).grid(row=i // 4, column=(i % 4) * 2, padx=6, pady=6, sticky="w")
            entry = ttk.Entry(form, width=26)
            entry.grid(row=i // 4, column=(i % 4) * 2 + 1, padx=6, pady=6, sticky="ew")
            key = lbl.split(" ")[0]
            self.product_fields[key] = entry

        self.product_fields["date"].insert(0, datetime.now().strftime(DATE_FMT))

        btn_bar = ttk.Frame(form)
        btn_bar.grid(row=3, column=0, columnspan=8, sticky="w", padx=6, pady=6)
        ttk.Button(btn_bar, text="Add Product", command=self.add_product).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Update Product", command=self.update_product).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Delete Product", command=self.delete_product).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Clear", command=self.clear_product_form).pack(side="left", padx=4)

        cols = ("id", "serial_number", "product", "entry_stock", "available_stock", "cost", "sell", "date", "vendor", "note")
        self.product_tree = ttk.Treeview(parent, columns=cols, show="headings", height=20)
        for c in cols:
            self.product_tree.heading(c, text=c.replace("_", " ").title())
            self.product_tree.column(c, anchor="w", width=120)

        self.product_tree.column("id", width=45)
        self.product_tree.column("note", width=220)
        self.product_tree.bind("<<TreeviewSelect>>", self.on_product_select)

        self.product_tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_sales_tab(self, parent):
        top = ttk.LabelFrame(parent, text="New Sale")
        top.pack(fill="x", padx=8, pady=8)

        self.sale_serial = ttk.Combobox(top, width=28, state="readonly")
        self.sale_qty = ttk.Entry(top, width=15)
        self.sale_date = ttk.Entry(top, width=20)
        self.sale_note = ttk.Entry(top, width=45)

        ttk.Label(top, text="Serial Number").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.sale_serial.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        ttk.Label(top, text="Quantity").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self.sale_qty.grid(row=0, column=3, padx=6, pady=6, sticky="w")
        ttk.Label(top, text="Sale Date (YYYY-MM-DD)").grid(row=0, column=4, padx=6, pady=6, sticky="w")
        self.sale_date.grid(row=0, column=5, padx=6, pady=6, sticky="w")
        ttk.Label(top, text="Note").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        self.sale_note.grid(row=1, column=1, columnspan=3, padx=6, pady=6, sticky="ew")
        ttk.Button(top, text="Process Sale", command=self.process_sale).grid(row=1, column=5, padx=6, pady=6)

        self.sale_date.insert(0, datetime.now().strftime(DATE_FMT))

        cols = ("id", "sale_date", "serial_number", "product", "quantity", "unit_sell", "total", "customer_note")
        self.sales_tree = ttk.Treeview(parent, columns=cols, show="headings", height=22)
        for c in cols:
            self.sales_tree.heading(c, text=c.replace("_", " ").title())
            self.sales_tree.column(c, anchor="w", width=150)

        self.sales_tree.column("id", width=45)
        self.sales_tree.column("customer_note", width=240)
        self.sales_tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_backup_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Local Backup")
        frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame, text="Export or import all product and sales data as JSON backup.").grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        ttk.Button(frame, text="Export Backup", command=self.export_backup).grid(row=1, column=0, padx=8, pady=8, sticky="w")
        ttk.Button(frame, text="Import Backup", command=self.import_backup).grid(row=1, column=1, padx=8, pady=8, sticky="w")

    def validate_date(self, value: str):
        datetime.strptime(value, DATE_FMT)

    def collect_product_form(self):
        data = {k: v.get().strip() for k, v in self.product_fields.items()}
        if not data["serial_number"] or not data["product"]:
            raise ValueError("Serial number and product are required.")
        self.validate_date(data["date"])
        data["entry_stock"] = int(data["entry_stock"])
        data["cost"] = float(data["cost"])
        data["sell"] = float(data["sell"])
        if data["entry_stock"] < 0:
            raise ValueError("Entry stock cannot be negative.")
        return data

    def add_product(self):
        try:
            payload = self.collect_product_form()
            self.db.add_product(payload)
            self.refresh_products()
            self.clear_product_form()
            messagebox.showinfo("Success", "Product added successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_product(self):
        if self.selected_product_id is None:
            messagebox.showwarning("Warning", "Select a product to update.")
            return
        try:
            payload = self.collect_product_form()
            self.db.update_product(self.selected_product_id, payload)
            self.refresh_products()
            self.refresh_sales()
            messagebox.showinfo("Success", "Product updated successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_product(self):
        if self.selected_product_id is None:
            messagebox.showwarning("Warning", "Select a product to delete.")
            return
        if not messagebox.askyesno("Confirm", "Delete selected product?"):
            return
        try:
            self.db.delete_product(self.selected_product_id)
            self.selected_product_id = None
            self.refresh_products()
            self.clear_product_form()
            messagebox.showinfo("Success", "Product deleted.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_product_form(self):
        for k, entry in self.product_fields.items():
            entry.delete(0, tk.END)
        self.product_fields["date"].insert(0, datetime.now().strftime(DATE_FMT))
        self.selected_product_id = None

    def on_product_select(self, _event):
        selected = self.product_tree.selection()
        if not selected:
            return
        vals = self.product_tree.item(selected[0], "values")
        self.selected_product_id = int(vals[0])
        mapping = {
            "serial_number": vals[1],
            "product": vals[2],
            "entry_stock": vals[3],
            "cost": vals[5],
            "sell": vals[6],
            "date": vals[7],
            "vendor": vals[8],
            "note": vals[9],
        }
        for k, v in mapping.items():
            self.product_fields[k].delete(0, tk.END)
            self.product_fields[k].insert(0, v)

    def refresh_products(self):
        for i in self.product_tree.get_children():
            self.product_tree.delete(i)

        rows = self.db.list_products()
        serials = []
        for row in rows:
            self.product_tree.insert("", tk.END, values=tuple(row))
            serials.append(row["serial_number"])

        self.sale_serial["values"] = serials
        self.refresh_sales()

    def process_sale(self):
        serial = self.sale_serial.get().strip()
        if not serial:
            messagebox.showwarning("Warning", "Please select serial number.")
            return
        try:
            qty = int(self.sale_qty.get().strip())
            self.validate_date(self.sale_date.get().strip())
            self.db.sell_item(serial, qty, self.sale_date.get().strip(), self.sale_note.get().strip())
            self.sale_qty.delete(0, tk.END)
            self.sale_note.delete(0, tk.END)
            self.refresh_products()
            self.refresh_sales()
            messagebox.showinfo("Success", "Sale processed and stock updated automatically.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh_sales(self):
        for i in self.sales_tree.get_children():
            self.sales_tree.delete(i)
        for row in self.db.list_sales():
            self.sales_tree.insert("", tk.END, values=tuple(row))

    def export_backup(self):
        file_path = filedialog.asksaveasfilename(
            title="Export backup",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if not file_path:
            return
        try:
            self.db.export_backup(Path(file_path))
            messagebox.showinfo("Success", "Backup exported.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def import_backup(self):
        file_path = filedialog.askopenfilename(
            title="Import backup",
            filetypes=[("JSON Files", "*.json")],
        )
        if not file_path:
            return
        if not messagebox.askyesno("Confirm", "This will replace current data. Continue?"):
            return
        try:
            self.db.import_backup(Path(file_path))
            self.refresh_products()
            self.refresh_sales()
            messagebox.showinfo("Success", "Backup imported.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    app = App()
    app.mainloop()
