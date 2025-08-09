import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import filedialog

BASE_URL = "https://www.pesuacademy.com"
LOGIN_URL = f"{BASE_URL}/Academy/j_spring_security_check"
SEMESTERS_URL = f"{BASE_URL}/Academy/a/studentProfilePESU/getStudentSemestersPESU"
SUBJECTS_URL = f"{BASE_URL}/Academy/s/studentProfilePESUAdmin"


def _slugify(text: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9\-_. ]+", "", text or "").strip()
    t = re.sub(r"\s+", "_", t)
    return t or "untitled"


def _guess_ext_from_content_type(ct: str) -> str:
    if not ct:
        return ".pdf"
    ct = ct.lower()
    if "pdf" in ct:
        return ".pdf"
    if any(x in ct for x in ["powerpoint", "presentation", "ppt"]):
        return ".pptx"
    if any(x in ct for x in ["msword", "word", "doc"]):
        return ".docx"
    if "zip" in ct:
        return ".zip"
    return ".bin"


def _parse_range_selection(text: str, max_n: int) -> list:
    s = (text or "").strip()
    if not s or s == "-":
        return list(range(1, max_n + 1))
    if "-" in s:
        a, b = s.split("-", 1)
        a = a.strip()
        b = b.strip()
        start = 1 if a == "" else int(a)
        end = max_n if b == "" else int(b)
        if start > end:
            start, end = end, start
        start = max(1, min(max_n, start))
        end = max(1, min(max_n, end))
        return list(range(start, end + 1))
    try:
        n = int(s)
        if 1 <= n <= max_n:
            return [n]
    except ValueError:
        pass
    return []


def _print_table(headers: list, rows: list) -> None:
    max_row_cols = max((len(r) for r in rows), default=0)
    num_cols = max(len(headers), max_row_cols)
    if num_cols == 0:
        print("(empty)")
        return
    widths = [0] * num_cols
    for i in range(num_cols):
        if i < len(headers):
            widths[i] = max(widths[i], len(headers[i]))
        for row in rows:
            cell = row[i] if i < len(row) else ""
            widths[i] = max(widths[i], len(cell))
    def fmt_row(row):
        cells = [(row[i] if i < len(row) else "") for i in range(num_cols)]
        return " | ".join(cells[i].ljust(widths[i]) for i in range(num_cols))
    if headers:
        print(fmt_row(headers))
        print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))


def login(session: requests.Session, username: str, password: str) -> bool:
    resp = session.get(f"{BASE_URL}/Academy/")
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_token = soup.find("meta", {"name": "csrf-token"})["content"]
    headers = {
        "X-CSRF-Token": csrf_token,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"{BASE_URL}/Academy/",
    }
    payload = {"j_username": username, "j_password": password}
    login_resp = session.post(LOGIN_URL, data=payload, headers=headers)
    return login_resp.url.endswith("/Academy/s/studentProfilePESU")


def get_semesters(session: requests.Session):
    session.get(f"{BASE_URL}/Academy/s/studentProfilePESU")
    headers = {"Referer": f"{BASE_URL}/Academy/s/studentProfilePESU"}
    resp = session.get(SEMESTERS_URL, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    semesters = []
    for opt in soup.find_all("option"):
        value = opt.get("value")
        if value:
            semesters.append((value, opt.text.strip()))
    return semesters


def get_subjects_html(session: requests.Session, sem_id: str) -> str:
    # Refresh CSRF from profile page
    prof = session.get(f"{BASE_URL}/Academy/s/studentProfilePESU")
    soup = BeautifulSoup(prof.text, "html.parser")
    csrf = soup.find("meta", {"name": "csrf-token"})["content"]
    headers = {
        "Referer": f"{BASE_URL}/Academy/s/studentProfilePESU",
        "X-CSRF-Token": csrf,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    }
    clean_id = re.sub(r"[^0-9]", "", str(sem_id))
    data = {
        "controllerMode": "6403",
        "actionType": "38",
        "id": clean_id,
        "menuId": "653",
        "_csrf": csrf,
    }
    resp = session.post(SUBJECTS_URL, headers=headers, data=data)
    return resp.text


def parse_subjects_with_course_ids(html: str):
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="getStudentSubjectsBasedOnSemesters") or soup
    table = container.find("table")
    if not table:
        return [], []
    headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
    items = []
    onclick_re = re.compile(r"(clickoncoursecontent|clickOnCourseContent)\s*\(\s*'?\s*(\d+)\s*'?", re.IGNORECASE)
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        cells = [td.get_text(" ", strip=True) for td in tds]
        course_id = None
        row_html = str(tr)
        m = onclick_re.search(row_html)
        if m:
            course_id = m.group(2)
        items.append({"cells": cells, "course_id": course_id})
    return headers, items


def get_course_content(session: requests.Session, course_id: str) -> str:
    # Load the course tabs page (matches backup: actionType=42, id=<course_id>)
    # Refresh CSRF
    prof = session.get(f"{BASE_URL}/Academy/s/studentProfilePESU")
    soup = BeautifulSoup(prof.text, "html.parser")
    csrf = soup.find("meta", {"name": "csrf-token"})["content"]
    headers = {
        "Referer": f"{BASE_URL}/Academy/s/studentProfilePESU",
        "X-CSRF-Token": csrf,
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }
    resp = session.get(
        SUBJECTS_URL,
        params={
            "controllerMode": "6403",
            "actionType": "42",
            "id": str(course_id),
            "menuId": "653",
            "_csrf": csrf,
        },
        headers=headers,
    )
    return resp.text


def extract_units_from_tabs(course_html: str):
    soup = BeautifulSoup(course_html, "html.parser")
    result = []
    ul = soup.find(id="courselistunit")
    if not ul:
        return result
    for a in ul.find_all("a"):
        text = a.get_text(" ", strip=True)
        m = re.search(r"Unit\s*(\d+)", text, re.IGNORECASE)
        num = int(m.group(1)) if m else None
        uid = None
        onclick = a.get("onclick")
        if onclick:
            m2 = re.search(r"handleclassUnit\s*\(\s*'?(\d+)'?\s*\)", onclick, re.IGNORECASE)
            if m2:
                uid = m2.group(1)
        if not uid:
            href = a.get("href", "")
            m3 = re.search(r"courseUnit_(\d+)", href)
            if m3:
                uid = m3.group(1)
        result.append({"number": num, "title": text, "unit_id": uid})
    return result


def fetch_live_unit_content(session: requests.Session, unit_id: str) -> str:
    resp = session.get(
        SUBJECTS_URL,
        params={
            "controllerMode": "6403",
            "actionType": "43",
            "coursecontentid": str(unit_id),
            "menuId": "653",
            "subType": "3",
            "_": str(int(time.time() * 1000)),
        },
        headers={
            "Referer": f"{BASE_URL}/Academy/s/studentProfilePESU",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    return resp.text


def parse_live_unit_classes(live_html: str):
    soup = BeautifulSoup(live_html, "html.parser")
    table = soup.find("table")
    if not table:
        return [], []
    headers = [th.get_text(" ", strip=True) for th in (table.thead.find_all("th") if table.thead else table.find_all("th"))]
    items = []
    onclick_re = re.compile(r"handleclasscoursecontentunit\s*\(\s*'([^']+)'\s*,\s*'?(\d+)'?\s*,\s*'?(\d+)'?\s*,\s*'?(\d+)'?\s*,\s*'?(\d+)'?", re.IGNORECASE)
    for tr in (table.tbody.find_all("tr") if table.tbody else table.find_all("tr")):
        tds = tr.find_all("td")
        if not tds:
            continue
        title = tds[0].get_text(" ", strip=True)
        args = None
        for el in [tr, tds[0]] + tds[0].find_all("a"):
            onclick = el.get("onclick") if hasattr(el, 'get') else None
            if onclick:
                m = onclick_re.search(onclick)
                if m:
                    args = m.groups()
                    break
        resource_counts = []
        for td in tds[1:]:
            a = td.find("a")
            txt = a.get_text(" ", strip=True) if a else td.get_text(" ", strip=True)
            cnt = re.search(r"(\d+)", txt)
            resource_counts.append(cnt.group(1) if cnt else (txt or "-"))
        items.append({
            "title": title,
            "resource_counts": resource_counts,
            "args": {
                "uuid": args[0] if args else None,
                "courseId": args[1] if args else None,
                "unitId": args[2] if args else None,
                "classNo": args[3] if args else None,
                "resourceType": args[4] if args else None,
            }
        })
    return headers, items


def fetch_preview_and_ids(session: requests.Session, entry: dict):
    slides = entry.get("args") or {}
    courseunitid = slides.get("uuid")
    subjectid = slides.get("courseId")
    coursecontentid = slides.get("unitId")
    classNo = slides.get("classNo")
    rtype = slides.get("resourceType") or "2"
    if not (courseunitid and subjectid):
        return [], ""
    # Try actionType=60 first
    h = {
        "Referer": f"{BASE_URL}/Academy/s/studentProfilePESU",
        "X-Requested-With": "XMLHttpRequest",
    }
    # refresh CSRF
    prof = session.get(f"{BASE_URL}/Academy/s/studentProfilePESU")
    soup = BeautifulSoup(prof.text, "html.parser")
    csrf = soup.find("meta", {"name": "csrf-token"})["content"]
    h["X-CSRF-Token"] = csrf
    p60 = {
        "controllerMode": "6403",
        "actionType": "60",
        "selectedData": str(subjectid),
        "id": "2",
        "unitid": str(courseunitid),
        "menuId": "653",
        "_": str(int(time.time() * 1000)),
    }
    r60 = session.get(SUBJECTS_URL, params=p60, headers=h)
    html = r60.text or ""
    ids = set(re.findall(r"downloadcoursedoc\s*\(\s*['\"]([a-f0-9\-]{6,})['\"]", html, flags=re.IGNORECASE))
    if ids:
        return list(ids), html
    # Fallback to actionType=343
    if not (coursecontentid and classNo):
        return [], html
    p343 = {
        "controllerMode": "9978",
        "actionType": "343",
        "courseunitid": str(courseunitid),
        "subjectid": str(subjectid),
        "coursecontentid": str(coursecontentid),
        "classNo": str(classNo),
        "type": str(rtype),
        "menuId": "653",
        "selectedData": "0",
        "_": str(int(time.time() * 1000)),
    }
    r343 = session.get(SUBJECTS_URL, params=p343, headers=h)
    html = r343.text or html
    ids = set(re.findall(r"downloadcoursedoc\s*\(\s*['\"]([a-f0-9\-]{6,})['\"]", html, flags=re.IGNORECASE))
    if not ids:
        ids = set(re.findall(r"href=['\"][^'\"]*download(?:slide)?coursedoc/([a-f0-9\-]{6,})", html, flags=re.IGNORECASE))
    return list(ids), html


def download_by_ids(session: requests.Session, doc_ids: list, si_no: int, title: str, out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    headers = {
        "Referer": f"{BASE_URL}/Academy/s/studentProfilePESU",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    }
    for i, did in enumerate(doc_ids, 1):
        url = f"{BASE_URL}/Academy/a/referenceMeterials/downloadslidecoursedoc/{did}"
        resp = session.get(url, headers=headers, allow_redirects=True)
        if resp.status_code != 200 or not resp.content:
            continue
        ct = resp.headers.get("Content-Type", "")
        cd = resp.headers.get("Content-Disposition", "")
        filename = None
        m = re.search(r"filename\*=UTF-8''([^;]+)", cd)
        if m:
            filename = m.group(1)
        else:
            m = re.search(r"filename=\"?([^\";]+)\"?", cd)
            if m:
                filename = m.group(1)
        if not filename:
            ext = _guess_ext_from_content_type(ct)
            suffix = f"_{i}" if len(doc_ids) > 1 else ""
            filename = f"{si_no:02d}{suffix}_{_slugify(title)}{ext}"
        path = os.path.join(out_dir, filename)
        try:
            with open(path, "wb") as f:
                f.write(resp.content)
            print("Saved:", path)
            saved.append(path)
        except Exception:
            pass
    return saved


def main():
    session = requests.Session()
    print("=== PESU Academy CLI ===")
    username = input("Username: ")
    password = input("Password: ")
    if not login(session, username, password):
        print("Login failed")
        return

    semesters = get_semesters(session)
    if not semesters:
        print("No semesters found")
        return
    print("\nSelect a semester:")
    for i, (sid, sname) in enumerate(semesters, 1):
        print(f"{i}. {sname} ({sid})")
    try:
        si = int(input("Enter choice number: "))
        if si < 1 or si > len(semesters):
            raise ValueError()
    except ValueError:
        print("Invalid choice")
        return
    sem_id = semesters[si - 1][0]

    # Load subjects page and list for the selected semester
    subjects_html = get_subjects_html(session, sem_id)
    sub_headers, sub_items = parse_subjects_with_course_ids(subjects_html)
    if not sub_items:
        print("No subjects parsed")
        print((subjects_html or "")[:500].replace("\n", " "))
        return
    print("\nSubjects:")
    rows = [it["cells"] for it in sub_items]
    _print_table(sub_headers, rows)

    # Choose course by row number (same indexing as table rows)
    try:
        ci = int(input("Select a course row: "))
    except ValueError:
        print("Invalid selection")
        return
    if ci < 1 or ci > len(sub_items) or not sub_items[ci - 1].get("course_id"):
        print("Invalid selection")
        return
    course_id = sub_items[ci - 1]["course_id"]

    # Fetch course page and units
    course_html = get_course_content(session, course_id)
    units = extract_units_from_tabs(course_html)
    if not units:
        print("No units found")
        print((course_html or "")[:500].replace("\n", " "))
        return
    print("\nSelect a unit:")
    for i, u in enumerate(units[:4], 1):
        print(f"{i}. {u['title']}")
    try:
        ui = int(input("Enter unit number (1-4): "))
        if ui < 1 or ui > len(units[:4]):
            raise ValueError()
    except ValueError:
        print("Invalid unit selection")
        return
    unit_id = units[ui - 1]["unit_id"]

    # Fetch live unit classes
    live_html = fetch_live_unit_content(session, unit_id)
    class_headers, class_items = parse_live_unit_classes(live_html)
    if not class_items:
        print("No classes found")
        return
    # Condensed display: SI No., Name, Slides
    slides_idx = None
    if class_headers:
        for i, h in enumerate(class_headers):
            if "slides" in h.lower():
                slides_idx = i
                break
    condensed_headers = ["SI No.", "Name", "Slides"]
    condensed_rows = []
    for idx, item in enumerate(class_items):
        si_no = item.get("args", {}).get("classNo") or str(idx + 1)
        name = item.get("title") or ""
        rc = item.get("resource_counts", [])
        slides_val = rc[2] if len(rc) > 2 else "-"
        if slides_idx is not None and slides_idx < len(rc):
            slides_val = rc[slides_idx - 1] if slides_idx - 1 < len(rc) else slides_val
        condensed_rows.append([str(si_no), name, str(slides_val)])
    print("\nClasses:")
    _print_table(condensed_headers, condensed_rows)

    # Select slides range and folder, then download
    rng = input("\nEnter slides range (a-b, -b, a-, -, or single number): ")
    indices = _parse_range_selection(rng, len(class_items))
    if not indices:
        print("No valid selection")
        return

    root = tk.Tk(); root.withdraw()
    out_dir = filedialog.askdirectory(title="Select download folder")
    if not out_dir:
        print("No folder selected")
        return

    for idx in indices:
        entry = class_items[idx - 1]
        ids, _html = fetch_preview_and_ids(session, entry)
        if not ids:
            print(f"No slide documents for {idx}")
            continue
        download_by_ids(session, ids, idx, entry.get("title") or f"class_{idx}", out_dir)


if __name__ == "__main__":
    main()
