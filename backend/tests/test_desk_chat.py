import io

from openpyxl import Workbook


def _workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "06_Location_Register"
    ws.append(["Offices"])
    ws.append(["One row each."])
    ws.append(["Location Code", "Location Name", "Location Type"])
    ws.append(["GGN", "Gurugram Headquarters", "Headquarters"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_chat_answers_from_records(client, auth_headers):
    resp = client.post("/api/v1/desk/chat", json={"message": "how many offices do we have?"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert "office" in resp.json()["reply"].lower()


def test_chat_file_reads_and_saves_offices(client, auth_headers):
    files = {"file": ("offices.xlsx", _workbook(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/v1/desk/chat/file", files=files, data={"note": ""}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["synced"] is True
    assert "offices" in body["reply"].lower()
    assert body["upload"]["saved"] == 1
    again = client.post("/api/v1/desk/chat", json={"message": "which offices are on file?"}, headers=auth_headers)
    assert "Gurugram" in again.json()["reply"]


def test_unrecognised_workbook_is_explained_and_not_saved(client, auth_headers):
    wb = Workbook()
    ws = wb.active
    ws.title = "01_KPI_Domains"
    ws.append(["KPI catalogue"])
    ws.append(["Definitions only."])
    ws.append(["Domain Code", "Domain Name"])
    ws.append(["KPI-1", "Uptime"])
    buf = io.BytesIO()
    wb.save(buf)
    files = {"file": ("kpi.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/v1/desk/chat/file", files=files, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["synced"] is False
    assert "01_KPI_Domains" in body["reply"]
