from setuptools import setup, find_packages

setup(
    name="ollamaflow",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyside6>=6.4.0",
        "NodeGraphQt>=0.6.2",
        "requests>=2.25.0",
    ],
    entry_points={
        'console_scripts': [
            'ollamaflow=app:main',
        ],
    },
    description="A node-based UI for Ollama LLM workflows",
    author="OllamaFlow Team",
    author_email="example@example.com",
    url="https://github.com/example/ollamaflow",
)
