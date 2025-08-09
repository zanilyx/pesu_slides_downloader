# PESU Slides Downloader (CLI)

A Windows-friendly CLI to log into PESU Academy, select a semester, pick a course and unit, list classes, and download Slides for selected lessons to a folder you choose. (Its painful to download anything from pesuacadamy.com so i made this)

## What it does
- Logs in using your PESU Academy credentials (prompted at runtime)
- Fetches semesters, subjects (courses), units, and live class list
- Lets you choose a range of class indices (e.g., `1-4`, `-3`, `2-`, `-`, or `3`)
- Downloads slide files for those classes into a directory you pick via a system folder dialog

## Requirements
- Windows 10/11
- Python 3.9+
- Network access to `https://www.pesuacademy.com`

## Install
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python pesu_slides_downloader.py
```
Follow the prompts:
1) Username and password
2) Semester selection
3) Subject (course) row selection
4) Unit selection (first 4 shown)
5) Class range (e.g., `1-3`)
6) Choose a download folder (system dialog opens); files are saved there

## Notes
- This tool uses only Slides for the selected classes. It does not attempt any format conversions or PDF combining.
- If the website flow changes (IDs, actionTypes, or endpoints), you may need to update the script.
- If a page fails to return expected data, the tool will print a short HTML snippet to help diagnose parsing issues.

## Troubleshooting
- Login failed
  - Verify your credentials; try logging into PESU Academy in a browser.
- “No semesters found” / “No subjects parsed” / “No units found”
  - Run again; if persistent, share the printed snippet with the developer so selectors can be updated.
- “No classes found”
  - Some units may be empty or hidden; try another unit.
- Slides not downloading
  - Some classes may not expose slide documents. Try a different range.

## Disclaimer & Terms of Use
- This tool is provided for personal access to your own course materials only.
- Be respectful of PESU Academy’s Terms of Service and do not overload their servers.
- The author is not responsible for any misuse or account issues arising from use of this tool.

## License
See `LICENSE`. You may use this tool, but you may not modify or redistribute it without explicit prior written permission from the author. Contact the author for any reuse requests. 
