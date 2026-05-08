#!/usr/bin/env bash
# run_all_research.sh
# Execute this script from the ml_quant_finance_research directory
set -e
export PYTHONUTF8=1

echo "=========================================="
echo " Starting Full Research Pipeline Execution"
echo "=========================================="

BASE_DIR="$(pwd)"

echo ""
echo "--- 1. Running General Research Notebooks ---"
cd "$BASE_DIR/general_research/notebooks"
python ../run_notebooks.py

echo ""
echo "--- 2. Running Regime Engine (Quant Research) ---"
cd "$BASE_DIR/quant_research/regime_engine"
python run_engine.py --backfill

echo ""
echo "--- 3. Running PEAD Engine (Quant Research) ---"
cd "$BASE_DIR/quant_research/pead_engine"
python run_engine.py --backfill --refresh

echo ""
echo "--- 4. Running ML Research Notebooks ---"
cd "$BASE_DIR/ml_research/stock_ml_lab/notebooks"
for nb in *.ipynb; do
  if [ -f "$nb" ]; then
    echo "Executing $nb..."
    jupyter nbconvert --to notebook --execute --inplace "$nb" || echo "Warning: Failed to execute $nb, continuing..."
  fi
done

echo ""
echo "=========================================="
echo " Research Pipeline Completed Successfully"
echo "=========================================="
