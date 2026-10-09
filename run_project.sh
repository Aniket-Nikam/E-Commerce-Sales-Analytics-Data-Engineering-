#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
python -m src.cli all --rows 250000 --runs 5
python -m src.cli api-ingest
streamlit run src/dashboard.py

