"""Minimal Streamlit app."""

import streamlit as st

from src.ingestion import run_pipeline, scan_documents

st.set_page_config(page_title="rag-project", layout="wide")
st.title("rag-project")

if st.button("Re-ingest data/raw"):
    chunks = run_pipeline()
    st.success(f"Ingested {len(chunks)} chunk(s)")

st.subheader("Documents in data/raw")
for path in scan_documents():
    st.write(path.name)
