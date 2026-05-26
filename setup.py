from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ace-engine-sdk",
    version="0.1.0",
    author="YuqiPlus",
    author_email="silverwjq@163.com",
    description="AceEngine image quality evaluation SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YuqiPlus/ACEngine-Client",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)