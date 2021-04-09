"""
Miscellaneous testing code
"""
import json

import numpy.testing as npt

try:
    import pytest

    HAS_PYTEST = True

except ImportError:
    HAS_PYTEST = False


def _check_output(  # pylint: disable=too-many-locals,too-many-branches
    res, expected_output_file, rtol, update
):
    if not HAS_PYTEST:
        raise ImportError("pytest not installed, run `pip install pytest`")

    with open(expected_output_file, "r") as filehandle:
        expected_output = json.load(filehandle)

    if update:
        updated_output = {}

    for climate_model, checks in expected_output.items():
        res_cm = res.filter(climate_model=climate_model)

        if update:
            updated_output[climate_model] = []

        for filter_kwargs, expected_val in checks:
            err_msg = "{}".format(filter_kwargs)

            if update:
                filter_kwargs_in = {**filter_kwargs}

            check_units = filter_kwargs.pop("unit", None)
            quantile = filter_kwargs.pop("quantile")
            res_to_check = res_cm.filter(**filter_kwargs)

            if check_units is not None:
                res_to_check = res_to_check.convert_unit(check_units)

            if res_to_check.empty:
                raise AssertionError

            res_val = float(
                res_to_check.process_over(
                    ("climate_model", "run_id"), "quantile", q=quantile
                ).values
            )

            try:
                npt.assert_allclose(
                    res_val, expected_val, rtol=rtol, err_msg=err_msg,
                )
                if update:
                    new_val = expected_val
            except AssertionError:
                if update:
                    new_val = res_val
                else:
                    raise

            if update:
                updated_output[climate_model].append((filter_kwargs_in, new_val))

    if update:
        with open(expected_output_file, "w") as file_handle:
            json.dump(updated_output, file_handle, indent=4)

        pytest.skip("Updated {}".format(expected_output_file))
