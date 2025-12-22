import unittest
from chameleon import PageTemplate
from chameleon.astutil import Symbol
from chameleon.tales import StringExpr
from chameleon.test import MockTemplate
from chameleon.zpt import security

class TestHTMLTemplates(unittest.TestCase):
    def setUp(self):
        self.security_policy = security.SecurityPolicy()
    
    def test_template_1(self):
        template = PageTemplate('<h1>Hello, ${name}!</h1>')
        result = template({'name': 'Alice'}, policy=self.security_policy)
        self.assertEqual(result, '<h1>Hello, Alice!</h1>')
    
    def test_template_2(self):
        template = PageTemplate('<p>${content}</p>')
        result = template({'content': 'This is a test'}, policy=self.security_policy)
        self.assertEqual(result, '<p>This is a test</p>')
    
    def test_template_3(self):
        template = PageTemplate('<ul tal:repeat="item items"><li>${item}</li></ul>')
        result = template({'items': ['apple', 'banana', 'cherry']}, policy=self.security_policy)
        self.assertEqual(result, '<ul><li>apple</li><li>banana</li><li>cherry</li></ul>')

if __name__ == '__main__':
    unittest.main()