import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
import os

notebooks = [
    '01_correlation_engine.ipynb',
    '02_regime_detection.ipynb',
    '03_factor_model.ipynb',
    '04_black_litterman.ipynb'
]

for nb_name in notebooks:
    print(f"Running {nb_name}...")
    with open(nb_name, encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
    try:
        ep.preprocess(nb, {'metadata': {'path': '.'}})
    except Exception as e:
        print(f"Error running {nb_name}: {e}")
        raise
    with open(nb_name, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)
    print(f"Finished {nb_name}")
