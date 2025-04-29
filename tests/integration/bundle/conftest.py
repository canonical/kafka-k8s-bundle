#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Generator, cast

import jubilant
import pytest
from literals import BUNDLE_BUILD


def pytest_addoption(parser):
    """Defines pytest parsers."""
    parser.addoption("--tls", action="store_true", help="set tls for e2e tests")

    parser.addoption(
        "--bundle-file",
        action="store",
        help="name of the bundle zip when provided.",
        default=BUNDLE_BUILD,
    )

    parser.addoption(
        "--model",
        action="store",
        help="Juju model to use; if not provided, a new model "
        "will be created for each test which requires one",
        default=None,
    )

    parser.addoption(
        "--keep-models",
        action="store_true",
        default=False,
        help="keep temporarily-created models",
    )


def pytest_generate_tests(metafunc):
    """Processes pytest parsers."""
    tls = metafunc.config.option.tls
    if "tls" in metafunc.fixturenames:
        metafunc.parametrize("tls", [bool(tls)], scope="module")

    bundle_file = metafunc.config.option.bundle_file
    if "bundle_file" in metafunc.fixturenames:
        metafunc.parametrize("bundle_file", [bundle_file], scope="module")


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """Pytest fixture that wraps :meth:`jubilant.with_model`.

    This adds command line parameter ``--keep-models`` (see help for details).
    """
    model = request.config.getoption("--model")
    keep_models = cast(bool, request.config.getoption("--keep-models"))

    if model is None:
        with jubilant.temp_model(keep=keep_models) as juju:
            yield juju
            log = juju.debug_log(limit=1000)
    else:
        juju = jubilant.Juju(model=model)
        yield juju
        log = juju.debug_log(limit=1000)

    if request.session.testsfailed:
        print(log, end="")
