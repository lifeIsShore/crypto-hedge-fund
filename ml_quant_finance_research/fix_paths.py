import os, glob, json

notebook_dir = r'c:\Users\ahmty\Desktop\hedge-fund\ml_quant_finance_research\general_research\notebooks'
for nb_file in glob.glob(os.path.join(notebook_dir, '*.ipynb')):
    with open(nb_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    for cell in data.get('cells', []):
        if cell.get('cell_type') == 'code':
            for i, line in enumerate(cell.get('source', [])):
                if "PORTFOLIO_ROOT = os.path.join(RESEARCH_ROOT, '..', 'portfolio')" in line:
                    cell['source'][i] = line.replace(
                        "os.path.join(RESEARCH_ROOT, '..', 'portfolio')",
                        "os.path.join(RESEARCH_ROOT, '..', '..', 'portfolio')"
                    )
                    modified = True
    
    if modified:
        with open(nb_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
        print(f'Fixed {os.path.basename(nb_file)}')
