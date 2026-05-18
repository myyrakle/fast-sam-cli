#!/usr/bin/env python

from setuptools import setup

# This fork intentionally exposes a distinct executable name so it can be
# installed alongside the upstream AWS SAM CLI without shadowing `sam`.
# All other metadata (name, version, dependencies, etc.) is defined in pyproject.toml.
cmd_name = "fsam"

setup(
    entry_points={
        "console_scripts": [f"{cmd_name}=samcli.cli.main:cli"],
    },
)
