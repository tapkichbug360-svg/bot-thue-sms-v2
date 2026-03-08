from setuptools import setup
from Cython.Build import cythonize
import glob
import sys

# Lấy tất cả file .py
py_files = glob.glob('*.py') + glob.glob('handlers/*.py') + glob.glob('database/*.py')
py_files = [f for f in py_files if not f.endswith('setup.py') and not f.endswith('run.py')]
print(f"📋 Biên dịch {len(py_files)} files với MinGW")

# Tùy chọn đặc biệt cho GCC
extra_compile_args = ['-O2', '-Wno-error']
extra_link_args = ['-static-libgcc']

setup(
    name='bot_thue_sms',
    ext_modules=cythonize(
        py_files,
        compiler_directives={
            'language_level': '3',
            'boundscheck': False,
            'wraparound': False,
            'initializedcheck': False
        },
        annotate=False
    ),
    options={
        'build_ext': {
            'inplace': True,
            'compiler': 'mingw32'
        }
    }
)
