"""Write answers using only the standard library. The short track fills the
bundled official template, retaining all identifiers, dates and formatting.
Long tracks use the one-sheet layout provided by the official starter examples."""
import csv
import io
import zipfile
import re
import math
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


def write_zip(path, files):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)


def write_workbook(path, raw, track, note="hackathon-ensemble 모델이 생성한 예측값입니다. 단위는 공식 가격 자료와 같습니다."):
    """Fill the official short template; retain the existing long-track writer."""
    if track != "short":
        return _write_legacy_workbook(path, raw, track, note)
    template = Path(__file__).with_name("official_short_template.xlsx")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))[1:]
    with zipfile.ZipFile(template) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    key = "xl/worksheets/sheet1.xml"
    xml = files[key].decode("utf-8")
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cells = {c.attrib["r"]: c for c in ET.fromstring(xml).findall(".//x:sheetData/x:row/x:c", ns)}
    def value(ref):
        return cells[ref].find("x:v", ns).text
    if len(rows) != 120:
        raise ValueError("The official short template requires 120 prediction rows")
    for number, row in enumerate(rows, 5):
        expected_id = "문제 " + row[0].removeprefix("C")
        if value(f"A{number}") != expected_id or value(f"B{number}")[:10] != row[1] or value(f"C{number}")[:10] != row[2]:
            raise ValueError(f"Prediction identifiers/dates do not match official row {number}")
        for col, price in zip("DEFGH", row[3:6] + [row[7], row[6]]):
            if not math.isfinite(float(price)) or float(price) <= 0:
                raise ValueError(f"Invalid price at {col}{number}")
            address = f"{col}{number}"
            # Only blank price cells change; all original styling and other XML remain.
            pattern = rf'<x:c r="{address}"([^>]*)\s*/>'
            xml, count = re.subn(pattern, lambda m: f'<x:c r="{address}"{m.group(1)}><x:v>{price}</x:v></x:c>', xml)
            if count != 1:
                raise ValueError(f"Expected one blank template cell at {address}")
    files[key] = xml.encode("utf-8")
    write_zip(path, files)


def _write_legacy_workbook(path, raw, track, note):
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    short = track == "short"
    identity = 3 if short else 4
    headers = ["문제번호", "기준일"] + (["예측할 날짜"] if short else ["예측 시작일", "예측 종료일"])
    headers += [name + (" 가격" if short else " 평균가격") for name in ["배추", "무", "양파", "건고추", "마늘"]]

    def cell(col, row, value, numeric=False):
        address = chr(65 + col) + str(row)
        if numeric:
            return f'<c r="{address}"><v>{value}</v></c>'
        return f'<c r="{address}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
    xml = ['<row r="1">' + cell(0, 1, "농산물 가격예측 제출 답안") + "</row>",
           '<row r="2">' + cell(0, 2, note) + "</row>",
           '<row r="4">' + "".join(cell(i, 4, value) for i, value in enumerate(headers)) + "</row>"]
    for number, row in enumerate(rows[1:], 5):
        # Official Excel orders dried pepper before garlic; the CSV orders garlic first.
        values = row[:identity] + row[identity:identity + 3] + [row[identity + 4], row[identity + 3]]
        xml.append(f'<row r="{number}">' + "".join(cell(i, number, v, i >= identity) for i, v in enumerate(values)) + "</row>")
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="예측가격" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="14" customWidth="1"/><col min="2" max="{identity}" width="16" customWidth="1"/><col min="{identity+1}" max="{len(headers)}" width="19" customWidth="1"/></cols><sheetData>{"".join(xml)}</sheetData></worksheet>',
    }
    write_zip(path, {name: value.encode("utf-8") for name, value in files.items()})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--track", choices=("short", "long1", "long2"), default="short")
    args = ap.parse_args()
    write_workbook(args.output, Path(args.csv).read_bytes(), args.track)
