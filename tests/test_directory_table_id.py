from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_JS = PROJECT_ROOT / "site" / "assets" / "app.js"


class DirectoryTableIdTests(unittest.TestCase):
    def test_id_column_precedes_source_column_and_row_cell(self):
        source = APP_JS.read_text(encoding="utf-8")
        columns = source.index('const directorySortColumns = [')
        id_column = source.index('{ key: "id", label: "ID"', columns)
        name_column = source.index('{ key: "name", label: "來源"', columns)
        row = source.index('function directoryTableRow(record)')
        id_cell = source.index('class="directory-id-cell"', row)
        source_cell = source.index('class="directory-source-cell"', row)

        self.assertLess(id_column, name_column)
        self.assertLess(id_cell, source_cell)
        self.assertIn('entry.publicId || "-"', source[id_cell:source_cell])


if __name__ == "__main__":
    unittest.main()
