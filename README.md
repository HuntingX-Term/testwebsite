# Enterprise Stock Management (Windows EXE Ready)

This project includes a professional desktop stock management application built with Python + Tkinter + SQLite.

## Features

- Product inventory fields:
  - Serial Number
  - Product
  - Entry Stock
  - Available Stock (auto-calculated)
  - Cost
  - Sell
  - Date
  - Vendor
  - Note
- Selling Items module:
  - Select product by serial number
  - Add quantity and sale details
  - Available stock decreases automatically after each sale
- Local backup:
  - Export full data (products + sales) to JSON
  - Import JSON backup to restore data

## Run locally

```bash
python3 stock_manager.py
```

## Build a real Windows `.exe`

On a Windows machine with Python installed:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name EnterpriseStockManager stock_manager.py
```

The final EXE will be generated in:

- `dist/EnterpriseStockManager.exe`

## Data storage

- Local SQLite database file: `stock_manager.db`
- Backup files: user-selected `.json`

## Notes

- Date format: `YYYY-MM-DD`
- The app prevents selling more than available stock.
