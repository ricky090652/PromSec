import unittest
from chameleon import PageTemplate
from zope.interface import Interface
from zope.securitypolicy.interfaces import IRole
from zope.securitypolicy.security import Role

class IMyInterface(Interface):
    pass

class TestChameleonTemplate(unittest.TestCase):

    def test_template_rendering(self):
        template = PageTemplate('Hello, ${name}!')
        result = template({'name': 'Alice'})
        self.assertEqual(result, 'Hello, Alice!')

    def test_attribute_handling(self):
        template = PageTemplate('<div tal:attributes="class python: \'active\' if active else \'\'"></div>')
        result = template({'active': True})
        self.assertEqual(result, '<div class="active"></div>')

    def test_interpolation(self):
        template = PageTemplate('The answer is ${2 + 2}.')
        result = template({})
        self.assertEqual(result, 'The answer is 4.')

    def test_error_handling(self):
        template = PageTemplate('${1/0}')
        with self.assertRaises(ZeroDivisionError):
            template({})

    def test_traversal(self):
        template = PageTemplate('<div tal:content="structure provider"></div>')
        result = template({'provider': 'Hello, world!'})
        self.assertEqual(result, '<div>Hello, world!</div>')

class TestSecurityPolicy(unittest.TestCase):

    def test_role_interface(self):
        role = Role('Editor')
        self.assertTrue(IRole.providedBy(role))

    def test_security_policy(self):
        role = Role('Editor')
        self.assertTrue(role.checkPermission('edit', None))

if __name__ == '__main__':
    unittest.main()