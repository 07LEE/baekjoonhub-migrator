#!/usr/bin/env python3
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from migrator import PathMapper


class TestPathMapper(unittest.TestCase):

    def setUp(self):
        PathMapper.SQL_CACHE.clear()

    def test_case_a_lang_first_to_platform_first(self):
        # Case A: Top dir is language (Python), sub dir is platform (백준)
        path = "Python/백준/Bronze/1000.py"
        transformed = PathMapper.transform_path(path, "platform_first")
        self.assertEqual(transformed, "백준/Bronze/1000.py")

    def test_case_a_lang_first_keep_language_first(self):
        path = "Python/백준/Bronze/1000.py"
        transformed = PathMapper.transform_path(path, "language_first")
        self.assertEqual(transformed, "Python/백준/Bronze/1000.py")

    def test_case_b_platform_top_to_language_first(self):
        # Case B: Top dir is platform (백준)
        path = "백준/Bronze/1000.py"
        transformed = PathMapper.transform_path(path, "language_first")
        self.assertEqual(transformed, "Python/백준/Bronze/1000.py")

    def test_case_b_platform_top_keep_platform_first(self):
        path = "백준/Bronze/1000.py"
        transformed = PathMapper.transform_path(path, "platform_first")
        self.assertEqual(transformed, "백준/Bronze/1000.py")

    def test_python3_normalization(self):
        path = "Python3/백준/Bronze/1000.py"
        transformed = PathMapper.transform_path(path, "language_first")
        self.assertEqual(transformed, "Python/백준/Bronze/1000.py")

    def test_programmers_level_normalization(self):
        path = "프로그래머스/lv1/12345/solution.py"
        transformed_plat = PathMapper.transform_path(path, "platform_first")
        self.assertEqual(transformed_plat, "프로그래머스/1/12345/solution.py")

        transformed_lang = PathMapper.transform_path(path, "language_first")
        self.assertEqual(transformed_lang, "Python/프로그래머스/1/12345/solution.py")

    def test_unrecognized_path_unchanged(self):
        path = "random_folder/some_file.txt"
        transformed = PathMapper.transform_path(path, "platform_first")
        self.assertEqual(transformed, "random_folder/some_file.txt")

    def test_sql_dialect_detection_oracle(self):
        content = "SELECT NVL(col1, 'default') FROM my_table WHERE ROWNUM <= 10;"
        dialect = PathMapper.detect_sql_dialect(content)
        self.assertEqual(dialect, "Oracle")

    def test_sql_dialect_detection_mysql(self):
        content = "SELECT IFNULL(col1, 'default') FROM my_table LIMIT 10;"
        dialect = PathMapper.detect_sql_dialect(content)
        self.assertEqual(dialect, "MySQL")

    def test_sql_dialect_detection_phone_number_not_oracle(self):
        # Column named PHONE_NUMBER should not trigger Oracle detection
        content = "SELECT PHONE_NUMBER FROM USERS LIMIT 5;"
        dialect = PathMapper.detect_sql_dialect(content)
        self.assertEqual(dialect, "MySQL")

    def test_sql_path_transformation(self):
        oracle_content = "SELECT NVL(a, b) FROM t;"
        getter = lambda sha: oracle_content
        path = "SQL/백준/1234.sql"
        transformed = PathMapper.transform_path(path, "language_first", content_getter=getter, blob_sha="sha123")
        self.assertEqual(transformed, "Oracle/백준/1234.sql")

    def test_flat_mode(self):
        path = "Python/백준/Bronze/1000.py"
        transformed = PathMapper.transform_path(path, "flat")
        self.assertEqual(transformed, "백준/Bronze/1000.py")


if __name__ == '__main__':
    unittest.main()
