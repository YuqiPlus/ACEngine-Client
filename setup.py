from pathlib import Path
from setuptools import find_packages, setup

with (Path(__file__).parent / "README.md").open("r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ace-engine-sdk",
    version="0.2.0",
    author="YuqiPlus",
    author_email="silverwjq@163.com",
    description="AceEngine image quality evaluation SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YuqiPlus/ACEngine-Client",
    project_urls={
        "Documentation": "https://github.com/YuqiPlus/ACEngine-Client#readme",
        "Source": "https://github.com/YuqiPlus/ACEngine-Client",
        "Issues": "https://github.com/YuqiPlus/ACEngine-Client/issues",
    },
    license_expression="MIT",
    license_files=["LICENSE"],
    packages=find_packages(include=["ace_engine", "ace_engine.*"]),
    install_requires=[
        "requests>=2.25.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)
