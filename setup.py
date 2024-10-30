from setuptools import setup

setup(
    version="2.0.0",
    name="dcm-bag-builder",
    description="build BagIt container",
    author="LZV.nrw",
    install_requires=[
        "bagit==1.*",
        "dcm-common>=3.0.0,<4.0.0",
    ],
    packages=["dcm_bag_builder"],
    package_data={"dcm_bag_builder": ["py.typed"]},
    setuptools_git_versioning={
        "enabled": True,
        "version_file": "VERSION",
        "count_commits_from_version_file": True,
        "dev_template": "{tag}.dev{ccount}",
    },
)
