@echo off
echo Starting Gate 2 Full Suite Run (7 Steps) > gate2_full_run.log
echo Check gate2_full_run.log for real-time progress.

echo [1/7] Running Holdout Baseline...
echo [1/7] Running Holdout Baseline >> gate2_full_run.log
python before-go-live/better-alpha/gate2_run.py --holdout-baseline >> gate2_full_run.log 2>&1

echo [2/7] Running DB Regime...
echo [2/7] Running DB Regime >> gate2_full_run.log
python before-go-live/better-alpha/gate2_run.py --family db_regime --n-seeds 3 --force >> gate2_full_run.log 2>&1

echo [3/7] Running PEAD...
echo [3/7] Running PEAD >> gate2_full_run.log
python before-go-live/better-alpha/gate2_run.py --family pead --n-seeds 3 --force >> gate2_full_run.log 2>&1

echo [4/7] Running Earnings...
echo [4/7] Running Earnings >> gate2_full_run.log
python before-go-live/better-alpha/gate2_run.py --family earnings --n-seeds 3 --force >> gate2_full_run.log 2>&1

echo [5/7] Running Crosssectional...
echo [5/7] Running Crosssectional >> gate2_full_run.log
python before-go-live/better-alpha/gate2_run.py --family crosssectional --n-seeds 3 --force >> gate2_full_run.log 2>&1

echo [6/7] Running Acceleration...
echo [6/7] Running Acceleration >> gate2_full_run.log
python before-go-live/better-alpha/gate2_run.py --family acceleration --n-seeds 3 --force >> gate2_full_run.log 2>&1

echo [7/7] Running Target Refinement...
echo [7/7] Running Target Refinement >> gate2_full_run.log
python before-go-live/better-alpha/gate2_run.py --family target_refinement --n-seeds 3 --force >> gate2_full_run.log 2>&1

echo Gate 2 Full Suite Run Complete! >> gate2_full_run.log
echo Done!
