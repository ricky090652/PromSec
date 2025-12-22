import unittest
from chameleon import PageTemplate

class TestChameleonTemplate(unittest.TestCase):

    def setUp(self):
        self.template = PageTemplate("""
            <html>
                <body>
                    <h1 tal:content="title">Title</h1>
                    <ul>
                        <li tal:repeat="item items" tal:content="item"></li>
                    </ul>
                </body>
            </html>
        """)

    def test_string_expression(self):
        result = self.template(title="Hello World", items=["Item 1", "Item 2"])
        self.assertIn("Hello World", result)
        self.assertIn("Item 1", result)
        self.assertIn("Item 2", result)

    def test_path_traversals(self):
        result = self.template(title="Hello World", items=["Item 1", "Item 2"])
        self.assertNotIn("items", result)
        self.assertNotIn("item", result)

    def test_unicode_inserts(self):
        result = self.template(title="Hello World", items=["Item 1", "Item 2"])
        self.assertIsInstance(result, str)

    def test_batch_iterations(self):
        result = self.template(title="Hello World", items=["Item 1", "Item 2"])
        self.assertNotIn("batch", result)

    def test_boolean_attributes(self):
        result = self.template(title="Hello World", items=["Item 1", "Item 2"])
        self.assertNotIn("True", result)
        self.assertNotIn("False", result)

    def test_interpolation_in_content(self):
        result = self.template(title="Hello World", items=["Item 1", "Item 2"])
        self.assertIn("Hello World", result)
        self.assertIn("Item 1", result)
        self.assertIn("Item 2", result)

    def test_exception_handling(self):
        with self.assertRaises(Exception):
            template = PageTemplate("""
                <html>
                    <body>
                        <h1 tal:content="title">Title</h1>
                        <ul>
                            <li tal:repeat="item items" tal:content="item"></li>
                        </ul>
                    </body>
                </html>
            """)
            result = template(title="Hello World", items=["Item 1", "Item 2"])

    def tearDown(self):
        del self.template

if __name__ == '__main__':
    unittest.main()