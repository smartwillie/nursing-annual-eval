import streamlit as st
import time
from generator import generate_evaluation

st.set_page_config(
    page_title="Nursing Annual Evaluation Generator",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] { background: #f4f7fb; }
[data-testid="stSidebar"] { background: #1e3a5f; }
[data-testid="stSidebar"] * { color: #e8f0f7 !important; }
[data-testid="stSidebar"] hr { border-color: #2d6a9f; }

/* ── Header banner ── */
.eval-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    color: white;
    padding: 1.6rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.6rem;
    text-align: center;
}
.eval-header h1 { margin: 0; font-size: 1.75rem; font-weight: 700; letter-spacing: .5px; }
.eval-header p  { margin: .3rem 0 0; font-size: .9rem; opacity: .85; }

/* ── Employee card ── */
.employee-card {
    background: white;
    border: 1px solid #dce6f0;
    border-left: 5px solid #2d6a9f;
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 6px rgba(0,0,0,.05);
}
.card-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1e3a5f;
    margin-bottom: 1rem;
}

/* ── Performance level badges ── */
.badge-exceeds  { background:#d4edda; color:#155724; padding:3px 10px; border-radius:20px; font-size:.82rem; font-weight:600; }
.badge-meets    { background:#cce5ff; color:#004085; padding:3px 10px; border-radius:20px; font-size:.82rem; font-weight:600; }
.badge-needs    { background:#fff3cd; color:#856404; padding:3px 10px; border-radius:20px; font-size:.82rem; font-weight:600; }

/* ── Output block ── */
.eval-output {
    background: #ffffff;
    border: 1px solid #cce0f5;
    border-left: 5px solid #28a745;
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    margin-top: .8rem;
    margin-bottom: 1.4rem;
    white-space: pre-wrap;
    font-family: Georgia, serif;
    font-size: .97rem;
    line-height: 1.7;
    color: #1a1a2e;
}
.output-name {
    font-size: 1rem;
    font-weight: 700;
    color: #1e3a5f;
    margin-bottom: .6rem;
}

/* ── Divider ── */
.section-divider { border: none; border-top: 2px dashed #d0dae6; margin: 1.8rem 0; }

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    border-radius: 8px;
    font-weight: 600;
    letter-spacing: .3px;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────
ROLES   = ["RN", "LPN", "CNA", "NA"]
LEVELS  = ["Exceeds Expectations", "Meets Expectations", "Needs Improvement"]
PARA_OPTIONS = [1, 2, 3, 4]

LEVEL_BADGE = {
    "Exceeds Expectations": "badge-exceeds",
    "Meets Expectations":   "badge-meets",
    "Needs Improvement":    "badge-needs",
}

# ── Session State ─────────────────────────────────────────────────────────────
if "employees" not in st.session_state:
    st.session_state.employees = [{}]   # list of dicts; one per card
if "results" not in st.session_state:
    st.session_state.results = {}       # keyed by employee index

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 Eval Generator")
    st.markdown("**Inpatient Nursing Unit**")
    st.markdown("---")

    mode = st.radio(
        "Evaluation Mode",
        ["Individual (1 employee)", "Batch (multiple employees)"],
        index=0,
    )
    is_batch = "Batch" in mode

    st.markdown("---")
    st.markdown("### Quick Help")
    st.markdown("""
**Performance Levels**
- 🟢 Exceeds Expectations
- 🔵 Meets Expectations
- 🟡 Needs Improvement

**Paragraph Count**
- 1 — compact summary
- 2 — standard (recommended)
- 3 — detailed narrative
- 4 — comprehensive review

**Tips**
- Be specific in notes
- Include dates / incidents
- Mention attendance issues
- Note certifications earned
""")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="eval-header">
  <h1>🏥 Annual Performance Evaluation Generator</h1>
  <p>Inpatient Nursing Unit &nbsp;·&nbsp; Aligned to Organizational Values &nbsp;·&nbsp; RN / LPN / CNA / NA</p>
</div>
""", unsafe_allow_html=True)

# ── Helper: render one employee form ─────────────────────────────────────────
def render_employee_form(idx: int, show_remove: bool):
    prefix = f"emp_{idx}"
    with st.container():
        st.markdown(f'<div class="employee-card">', unsafe_allow_html=True)
        header_col, remove_col = st.columns([8, 1])
        with header_col:
            st.markdown(f'<div class="card-title">👤 Employee {idx + 1}</div>', unsafe_allow_html=True)
        with remove_col:
            if show_remove and st.button("✕", key=f"remove_{idx}", help="Remove this employee"):
                st.session_state.employees.pop(idx)
                if idx in st.session_state.results:
                    del st.session_state.results[idx]
                st.rerun()

        c1, c2, c3, c4 = st.columns([3, 1.5, 2.5, 1.2])
        with c1:
            name = st.text_input("Employee Name", key=f"{prefix}_name",
                                 placeholder="e.g. Jane Smith")
        with c2:
            role = st.selectbox("Role", ROLES, key=f"{prefix}_role")
        with c3:
            level = st.selectbox("Performance Level", LEVELS, key=f"{prefix}_level")
        with c4:
            num_paragraphs = st.selectbox("Paragraphs", PARA_OPTIONS,
                                          index=1, key=f"{prefix}_paras")

        notes = st.text_area(
            "Manager's Notes / Staff Description",
            key=f"{prefix}_notes",
            height=160,
            placeholder=(
                "Describe this employee's performance in detail. Include:\n"
                "• Clinical skills, patient care observations\n"
                "• Specific incidents or examples\n"
                "• Teamwork, communication, leadership behaviors\n"
                "• Attendance: tardiness, absences, no-call/no-shows\n"
                "• Professional development: certifications, courses\n"
                "• Any strengths or areas needing improvement"
            ),
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return {"name": name, "role": role, "level": level,
                "num_paragraphs": num_paragraphs, "notes": notes}


# ── Employee forms ─────────────────────────────────────────────────────────────
if not is_batch:
    # Single employee — always exactly one card
    if len(st.session_state.employees) > 1:
        st.session_state.employees = [{}]
        st.session_state.results   = {}
    form_data = [render_employee_form(0, show_remove=False)]
else:
    form_data = []
    for i in range(len(st.session_state.employees)):
        data = render_employee_form(i, show_remove=len(st.session_state.employees) > 1)
        form_data.append(data)

    add_col, _ = st.columns([2, 8])
    with add_col:
        if st.button("＋ Add Employee", use_container_width=True):
            st.session_state.employees.append({})
            st.rerun()

# ── Generate buttons ──────────────────────────────────────────────────────────
st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

if is_batch:
    gen_col, clear_col = st.columns([3, 1])
    with gen_col:
        generate_all = st.button("⚡ Generate All Evaluations", type="primary",
                                 use_container_width=True)
    with clear_col:
        if st.button("🗑 Clear All", use_container_width=True):
            st.session_state.results = {}
            st.rerun()
    generate_single = None
else:
    generate_single = st.button("⚡ Generate Evaluation", type="primary",
                                use_container_width=True)
    generate_all    = None
    col2, _ = st.columns([1, 4])
    with col2:
        if st.button("🗑 Clear Result"):
            st.session_state.results = {}
            st.rerun()

# ── Generation logic ──────────────────────────────────────────────────────────
def validate_entry(entry: dict, idx: int) -> str | None:
    if not entry.get("name", "").strip():
        return f"Employee {idx + 1}: Name is required."
    if not entry.get("notes", "").strip():
        return f"Employee {idx + 1} ({entry['name']}): Manager's notes are required."
    return None

def run_generation(indices: list[int]):
    errors = []
    for i in indices:
        err = validate_entry(form_data[i], i)
        if err:
            errors.append(err)
    if errors:
        for e in errors:
            st.error(e)
        return

    progress_bar = st.progress(0, text="Generating evaluations…")
    total = len(indices)
    for step, i in enumerate(indices):
        e = form_data[i]
        name, role, level, paras, notes = (
            e["name"].strip(), e["role"], e["level"], e["num_paragraphs"], e["notes"].strip()
        )
        with st.spinner(f"Generating evaluation for {name}…"):
            try:
                result = generate_evaluation(name, role, level, notes, paras)
                st.session_state.results[i] = {"text": result, "name": name,
                                                "role": role, "level": level,
                                                "paras": paras}
            except Exception as ex:
                st.session_state.results[i] = {"error": str(ex), "name": name}
        progress_bar.progress((step + 1) / total,
                              text=f"Completed {step + 1} of {total}…")
        if step < total - 1:
            time.sleep(0.3)
    progress_bar.empty()
    st.success(f"✅ Generated {total} evaluation(s) successfully.")

if generate_all:
    run_generation(list(range(len(form_data))))
elif generate_single:
    run_generation([0])

# ── Results display ───────────────────────────────────────────────────────────
if st.session_state.results:
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("## 📄 Generated Evaluations")

    sorted_keys = sorted(st.session_state.results.keys())
    for i in sorted_keys:
        res = st.session_state.results[i]
        if "error" in res:
            st.error(f"**{res['name']}** — Generation failed: {res['error']}")
            continue

        badge_class = LEVEL_BADGE.get(res["level"], "badge-meets")
        st.markdown(
            f'<div class="output-name">'
            f'{res["name"]} &nbsp;·&nbsp; {res["role"]} &nbsp;·&nbsp; '
            f'<span class="{badge_class}">{res["level"]}</span> &nbsp;·&nbsp; '
            f'{res["paras"]} paragraph(s)'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Format paragraphs with spacing
        paragraphs = [p.strip() for p in res["text"].split("\n\n") if p.strip()]
        formatted  = "\n\n".join(paragraphs)
        st.markdown(f'<div class="eval-output">{formatted}</div>', unsafe_allow_html=True)

        # Copy / regenerate row
        btn1, btn2, _ = st.columns([1.8, 1.8, 6])
        with btn1:
            st.download_button(
                "⬇ Download (.txt)",
                data=f"{res['name']} — {res['role']} — {res['level']}\n\n{formatted}",
                file_name=f"eval_{res['name'].replace(' ', '_')}.txt",
                mime="text/plain",
                key=f"dl_{i}",
                use_container_width=True,
            )
        with btn2:
            if st.button("🔄 Regenerate", key=f"regen_{i}", use_container_width=True):
                run_generation([i])
                st.rerun()

    # ── Download all ──────────────────────────────────────────────────────────
    if len(st.session_state.results) > 1:
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        all_text_parts = []
        for i in sorted_keys:
            r = st.session_state.results[i]
            if "error" not in r:
                block = (f"{r['name']} — {r['role']} — {r['level']}\n"
                         + "=" * 60 + "\n\n"
                         + "\n\n".join([p.strip() for p in r["text"].split("\n\n") if p.strip()])
                         + "\n\n")
                all_text_parts.append(block)

        if all_text_parts:
            st.download_button(
                "⬇ Download All Evaluations (.txt)",
                data="\n".join(all_text_parts),
                file_name="all_evaluations.txt",
                mime="text/plain",
                use_container_width=False,
            )
