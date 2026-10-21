# Stock stand-in

Separate database from the desk and from Darwinbox: `stock.sqlite` in this folder.

It holds items per office: quantity on hand, reorder level, and expiry. A sync copies those figures into the desk. The office code must already exist on the desk. Quantity is what is on the shelf. It is not a payment.

Create or refresh the sample file:

```bash
cd backend
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '..'); from integrations.stock.source import ensure_seeded; print(ensure_seeded())"
```
