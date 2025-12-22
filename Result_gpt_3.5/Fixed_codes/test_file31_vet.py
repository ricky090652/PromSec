import os
import logging

from some_module import SomeClass

class CustomResolver:
    def resolve(self, input):
        # Custom resolution logic here
        pass

def create_sydent_instance():
    config = {
        'secret_key': os.getenv('SECRET_KEY'),
        'password': os.getenv('PASSWORD'),
        'other_config': 'value'
    }
    
    logging.basicConfig(level=logging.INFO)
    
    resolver = CustomResolver()
    
    sydent = Sydent(config, resolver)
    
    return sydent