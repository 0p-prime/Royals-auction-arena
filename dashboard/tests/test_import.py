import importlib.util, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('import_data',Path(__file__).parents[1]/'scripts/import_data.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class NumberTest(unittest.TestCase):
    def test_non_finite_is_null(self):
        for x in ['',None,'NaN','inf','-inf']:self.assertIsNone(module.number(x))
    def test_numeric(self):
        self.assertEqual(module.number('2.3'),2.3)
if __name__=='__main__':unittest.main()
