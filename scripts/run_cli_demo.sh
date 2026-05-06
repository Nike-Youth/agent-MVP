#!/usr/bin/env bash
cd "$(dirname "$0")/.."
python run_cli.py --thesis examples/sample_thesis.txt --ppt examples/sample_ppt.txt --school examples/school_requirements.txt --mock
