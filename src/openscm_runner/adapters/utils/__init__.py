"""
Utility functions for adapters
"""
from openscm_runner.adapters import get_adapters_classes


def get_adapter(climate_model):
    """
    Get an adapter for a given climate_model

    Parameters
    ----------
    climate_model: str
        The name of the model to fetch

        This parameter is case-insensitive

    Returns
    -------
    openscm_runner.adapters.base._Adapter
        The adapter for a given climate model
    """
    adapters_classes = get_adapters_classes()

    for Adapter in adapters_classes:
        if Adapter.model_name.upper() == climate_model.upper():
            return Adapter()

    raise NotImplementedError(f"No adapter available for {climate_model}")
