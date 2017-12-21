from setuptools import setup, find_packages

setup(
    name='notebook-exam',
    version='0.1',
    packages=find_packages(),    
    install_requires=[
        'Click',
    	'tabulate==0.8.2',
        'pandas',
        'colorama',
        'pysftp'
    ],
    entry_points={ 'console_scripts': ['notebook-exam=notebook_exam:cli'] },
)
