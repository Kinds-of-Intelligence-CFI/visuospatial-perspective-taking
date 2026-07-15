from setuptools import setup, find_packages
 
setup(
name="visual-perspective-taking",
version="0.1.0",
packages=find_packages(),
python_requires=">=3.8",
install_requires=[
    "inspect_ai",
    "jsonschema",
    "matplotlib",
    "numpy",
    "pandas",
    "pillow",
    "pydantic",
    "seaborn",
    ],
)