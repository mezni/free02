"""Streamlit app: ingest and inspect pipeline run history."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src.core.logging import setup_logging
from src.db.models import PipelineRun
from src.db.session import SessionLocal
from src.ingestion import PipelineConfig, run_pipeline, scan_documents

setup_logging()

st.set_page_config(page_title="rag-project", layout="wide")
st.title("rag-project")

# --- Ingest ---

if st.button("Re-ingest data/raw"):
    _, chunks = run_pipeline(PipelineConfig())
    st.success(f"Ingested {len(chunks)} chunk(s)")

st.subheader("Documents in data/raw")
for path in scan_documents():
    st.write(path.name)

# --- Run history ---

if st.button("Show Pipeline Runs"):
    st.session_state["_show_runs"] = not st.session_state.get("_show_runs", False)

if st.session_state.get("_show_runs", False):
    st.divider()
    st.subheader("Pipeline Run History")

    session = SessionLocal()
    try:
        runs = (
            session.query(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(20)
            .all()
        )
    finally:
        session.close()

    if not runs:
        st.info("No runs yet. Click **Re-ingest data/raw** to create the first run.")
    else:
        for run in runs:
            status = run.status
            if status == "success":
                badge = ":green[SUCCESS]"
            elif status == "failed":
                badge = ":red[FAILED]"
            else:
                badge = ":orange[RUNNING]"

            duration = (
                f"{run.duration_seconds:.1f}s"
                if run.duration_seconds is not None
                else "—"
            )

            st.markdown(
                f"**`{run.run_id[:8]}`** &nbsp; {badge} &nbsp; `{duration}` &nbsp; "
                f"Started: {run.started_at:%Y-%m-%d %H:%M}"
            )

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("New", run.files_new)
            col2.metric("Modified", run.files_modified)
            col3.metric("Deleted", run.files_deleted)
            col4.metric("Chunks", run.chunks_created)

            if run.error_message:
                st.error(run.error_message)

            st.caption(f"Unchanged: {run.files_unchanged}  |  Source: {run.source}")
            st.markdown("---")
