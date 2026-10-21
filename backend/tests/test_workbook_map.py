import io

from openpyxl import Workbook

from app.agent.importer import prepare_company_import


def _workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "06_Location_Register"
    ws.append(["6. CORPORATE OFFICES"])
    ws.append(["Enter one record per row."])
    ws.append(["Company Code", "Location Code", "Location Name", "Location Type", "Parent Location Code"])
    ws.append(["NSTG", "NST-GGN-HQ", "Gurugram Headquarters", "Headquarters", ""])
    ws.append(["NSTG", "NST-HYD-01", "Hyderabad Delivery Centre", "Manual", "NST-GGN-HQ"])
    people = wb.create_sheet("10_Key_Contacts")
    people.append(["10. CONTACTS"])
    people.append(["Enter one record per row."])
    people.append(["Full Name", "Email", "Designation/Role", "Location Code"])
    people.append(["Priya Nair", "priya.nair@novasphere.example", "Facilities", "NST-GGN-HQ"])
    people.append(["No Mail", "", "Facilities", "NST-GGN-HQ"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_titled_workbook_without_company_rows_is_not_sent_to_ai():
    wb = Workbook()
    ws = wb.active
    ws.title = "01_KPI_Domains"
    ws.append(["1. KPI AND ANALYTICS"])
    ws.append(["Part 10 defines enterprise KPIs."])
    ws.append(["Domain Code", "Domain Name", "Description"])
    ws.append(["KPI-1", "Uptime", "Share of tickets closed on time"])
    buf = io.BytesIO()
    wb.save(buf)
    try:
        prepare_company_import("kpi.xlsx", buf.getvalue())
    except ValueError as exc:
        assert "no offices" in str(exc)
    else:
        raise AssertionError("KPI workbook should not be imported")


def test_flexible_workbook_maps_without_calling_ai():
    bundles, source = prepare_company_import("offices.xlsx", _workbook())
    assert source == "mapped"
    assert [row["code"] for row in bundles["locations"]] == ["NST-GGN-HQ", "NST-HYD-01"]
    assert bundles["locations"][0]["type"] == "BRANCH"
    assert bundles["locations"][1]["parent_code"] == "NST-GGN-HQ"
    assert bundles["employees"] == [
        {
            "email": "priya.nair@novasphere.example",
            "name": "Priya Nair",
            "department": "",
            "role": "Facilities",
            "manager_email": "",
            "location": "NST-GGN-HQ",
        }
    ]
