"""Build the Anki add-on using only the Python standard library."""
from pathlib import Path
import ast
import json
import zipfile

root = Path(__file__).resolve().parent
source = root / 'word_piles'
output = root / 'dist/Word_Piles_0.1.0.ankiaddon'
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.suffix not in {'.py', '.json', '.md'}:
            continue
        if path.suffix == '.py':
            ast.parse(path.read_text())
        if path.suffix == '.json':
            json.loads(path.read_text())
        archive.write(path, path.name)
    for name in ('README.md', 'README.ru.md', 'LICENSE'):
        archive.write(root / name, name)
    for path in sorted((root / 'tests').glob('*.py')):
        archive.write(path, 'tests/' + path.name)
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    assert {'__init__.py', 'manifest.json'} <= set(archive.namelist())
print(output)
