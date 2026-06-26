import inspect
import pkgutil
import importlib

print('Python executable:', __import__('sys').executable)
try:
    import langchain.embeddings as le
    print('langchain.embeddings members:')
    names = [name for name,_ in inspect.getmembers(le) if not name.startswith('_')]
    print(names)
except Exception as e:
    print('Error importing langchain.embeddings:', e)

try:
    import ollama
    print('\nollama module path:', getattr(ollama, '__path__', None))
    if getattr(ollama, '__path__', None):
        print('ollama submodules:')
        for m in pkgutil.iter_modules(ollama.__path__):
            print(' -', m.name)
    else:
        print('No __path__ on ollama module')
except Exception as e:
    print('Error importing ollama:', e)

# Try to find OllamaEmbeddings in any installed package
candidates = ['langchain.embeddings', 'langchain_ollama', 'langchain_ollama.embeddings', 'ollama']
for c in candidates:
    try:
        mod = importlib.import_module(c)
        print(f'\nModule {c} members:')
        print([n for n,_ in inspect.getmembers(mod) if not n.startswith('_')][:200])
    except Exception as e:
        print(f'Could not import {c}:', e)
