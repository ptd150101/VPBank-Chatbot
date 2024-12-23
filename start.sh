#!/bin/bash

# Start backend
python source/run.py &

# Start frontend
streamlit run streamlit/streamlit.py --server.port 8501 --server.address 0.0.0.0

# Keep container running
wait 