# Darwinbox stand-in

Separate database from the desk and from stock: `darwinbox.sqlite` in this folder.

It holds offices and employees only. Running a sync copies them into the desk. An office code here must already exist on the desk (the same code used on the place). People who have left stay in this file with active = 0, and the sync marks them inactive. It does not invent a person who is not in this file.

Create or refresh the sample file:

```bash
cd backend
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '..'); from integrations.darwinbox.source import ensure_seeded; print(ensure_seeded())"
```
