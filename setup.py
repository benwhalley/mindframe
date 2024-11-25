# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['mindframe',
 'mindframe.management.commands',
 'mindframe.migrations',
 'mindframe.templatetags',
 'mindframe.tests']

package_data = \
{'': ['*'],
 'mindframe': ['static/mindframe/css/*',
               'static/mindframe/js/*',
               'templates/*',
               'templates/admin/*',
               'templates/admin/mindframe/intervention/*']}

install_requires = \
['Django>=5.0.6,<6.0.0',
 'black>=24.4.2,<25.0.0',
 'boto3>=1.34.119,<2.0.0',
 'celery>=5.4.0,<6.0.0',
 'dj-database-url>=2.1.0,<3.0.0',
 'django-autoslug>=1.9.9,<2.0.0',
 'django-environ>=0.11.2,<0.12.0',
 'django-lifecycle>=1.2.4,<2.0.0',
 'django-shortuuidfield>=0.1.3,<0.2.0',
 'gevent>=24.11,<25.0',
 'gradio>=5.5.0,<6.0.0',
 'gunicorn>=22.0.0,<23.0.0',
 'honcho>=1.1.0,<2.0.0',
 'instructor>=1.6.4,<2.0.0',
 'litellm>=1.51.0,<2.0.0',
 'magentic>=0.32.0,<0.33.0',
 'pandoc>=2.4,<3.0',
 'pgvector>=0.3.6,<0.4.0',
 'poetry-plugin-export>=1.8.0,<2.0.0',
 'pydantic>=2.9.2,<3.0.0',
 'python-box>=7.2.0,<8.0.0',
 'python-dotenv>=1.0.1,<2.0.0',
 'redis>=5.2,<6.0',
 'ruamel-yaml>=0.18.6,<0.19.0',
 'rules>=3.4,<4.0',
 'sentence-transformers>=3.3.0,<4.0.0',
 'shortuuid>=1.0.13,<2.0.0',
 'uvicorn>=0.30.1,<0.31.0']

extras_require = \
{':sys_platform == "darwin"': ['psycopg2_binary>=2.9,<3.0'],
 ':sys_platform == "linux"': ['psycopg2>=2.9,<3.0']}

entry_points = \
{'console_scripts': ['mindframe-bot = mindframe.chatbot:main']}

setup_kwargs = {
    'name': 'mindframe',
    'version': '0.1.11',
    'description': 'A Python package for the `mindframe` project',
    'long_description': 'None',
    'author': 'Ben Whalley',
    'author_email': 'ben.whalley@plymouth.ac.uk',
    'maintainer': 'None',
    'maintainer_email': 'None',
    'url': 'None',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'extras_require': extras_require,
    'entry_points': entry_points,
    'python_requires': '>=3.11,<4.0',
}


setup(**setup_kwargs)

