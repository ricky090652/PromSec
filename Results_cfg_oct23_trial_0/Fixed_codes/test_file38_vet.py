import unittest
from chameleon import PageTemplate
from zope.interface import Interface, implementer
from zope.securitypolicy.interfaces import IRole, IPrincipalRoleManager

class IMyTemplate(Interface):
    pass

@implementer(IMyTemplate)
class MyTemplate:
    def __init__(self, template_string):
        self.template = PageTemplate(template_string)

    def render(self, context):
        return self.template.render(**context)

class TestMyTemplate(unittest.TestCase):
    def setUp(self):
        self.template = MyTemplate('<h1>Hello ${name}!</h1>')

    def test_render(self):
        context = {'name': 'Alice'}
        result = self.template.render(context)
        self.assertEqual(result, '<h1>Hello Alice!</h1>')

if __name__ == '__main__':
    unittest.main()