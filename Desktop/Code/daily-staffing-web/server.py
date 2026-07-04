import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Flask, after_this_request, jsonify, render_template, request, send_file
from openpyxl import load_workbook

import build_roster
import medsurg

app = Flask(__name__)

JOBS_DIR = Path(tempfile.gettempdir()) / "daily-staffing-web-jobs"
JOBS_DIR.mkdir(exist_ok=True)

DATA_DIR = Path(__file__).parent / "data"
SUMMARY_PATH = DATA_DIR / "MedSurg_Assignments_Summary.xlsx"
medsurg.ensure_summary_exists(SUMMARY_PATH)

_summary_lock = threading.Lock()

ALLOWED_EXT = {".xlsx"}


def _save_upload(file_storage, dest_dir):
    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"'{file_storage.filename}' is not an .xlsx file")
    path = dest_dir / f"{uuid.uuid4().hex}{ext}"
    file_storage.save(path)
    return path


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/build", methods=["POST"])
def build_route():
    roster_file = request.files.get("roster")
    tracker_file = request.files.get("tracker")
    assignment_file = request.files.get("assignment")
    shift = request.form.get("shift") or None
    if shift not in ("day", "noc"):
        shift = None
    include_turn = request.form.get("include_turn") == "on"

    if not roster_file or not roster_file.filename:
        return jsonify({"ok": False, "error": "Please upload the Daily Roster file."}), 400
    if not tracker_file or not tracker_file.filename:
        return jsonify({"ok": False, "error": "Please upload the RN/CNA Rotation Tracker file."}), 400

    job_id = uuid.uuid4().hex
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        roster_path = _save_upload(roster_file, job_dir)
        tracker_path = _save_upload(tracker_file, job_dir)
        output_path = job_dir / "Final.xlsx"

        unmatched, detected_shift = build_roster.build(
            str(roster_path), str(tracker_path), str(output_path), shift_override=shift
        )

        turn_info = None
        if include_turn:
            with _summary_lock:
                if assignment_file and assignment_file.filename:
                    assignment_path = _save_upload(assignment_file, job_dir)
                    medsurg.append_assignment_file(str(assignment_path), str(SUMMARY_PATH))

                if detected_shift == "day":
                    shift_date, results, never_e, never_p, had_it = medsurg.compute_turn(
                        str(roster_path), str(SUMMARY_PATH)
                    )
                    wb = load_workbook(output_path)
                    medsurg.render_turn_sheet(wb, shift_date, results, never_e, never_p, had_it)
                    wb.save(output_path)
                    turn_info = {
                        "included": True,
                        "eligible_count": len(results),
                        "never_count": len(never_e) + len(never_p),
                    }
                else:
                    turn_info = {
                        "included": False,
                        "reason": "Turn tracker only applies to Day shift rosters (this roster was detected as NOC).",
                    }

        return jsonify({
            "ok": True,
            "download_url": f"/download/{job_id}",
            "unmatched": [{"name": n, "profile": p, "table": t} for n, p, t in unmatched],
            "turn": turn_info,
        })
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/download/<job_id>")
def download(job_id):
    if not job_id.isalnum():
        return "Not found", 404
    output_path = JOBS_DIR / job_id / "Final.xlsx"
    if not output_path.exists():
        return "File not found or already downloaded.", 404

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(JOBS_DIR / job_id, ignore_errors=True)
        except Exception:
            pass
        return response

    return send_file(output_path, as_attachment=True, download_name="Final.xlsx")


@app.route("/summary/append", methods=["POST"])
def summary_append():
    assignment_file = request.files.get("assignment")
    if not assignment_file or not assignment_file.filename:
        return jsonify({"ok": False, "error": "Please choose a Day Assignment export to upload."}), 400

    tmp_dir = JOBS_DIR / f"append-{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        assignment_path = _save_upload(assignment_file, tmp_dir)
        with _summary_lock:
            date_lbl, new_records = medsurg.append_assignment_file(str(assignment_path), str(SUMMARY_PATH))
        return jsonify({
            "ok": True,
            "date": date_lbl,
            "nurses": [{"name": n, "rooms": r, "count": c} for _, n, r, c in new_records],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route("/summary/download")
def summary_download():
    with _summary_lock:
        medsurg.ensure_summary_exists(SUMMARY_PATH)
        return send_file(SUMMARY_PATH, as_attachment=True, download_name="MedSurg_Assignments_Summary.xlsx")


@app.route("/summary/replace", methods=["POST"])
def summary_replace():
    file = request.files.get("summary")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Please choose a summary file to upload."}), 400

    tmp_path = JOBS_DIR / f"summary-upload-{uuid.uuid4().hex}.xlsx"
    try:
        file.save(tmp_path)
        medsurg.validate_summary_workbook(tmp_path)
        with _summary_lock:
            shutil.copy(tmp_path, SUMMARY_PATH)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5057))
    app.run(debug=False, host="0.0.0.0", port=port)
