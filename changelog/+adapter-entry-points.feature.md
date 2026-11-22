Added loading of adapters from other packages through the `openscm_runner.adapters` entry point group.
Packages declare an entry point that loads an {py:class}`openscm_runner.adapters.base._Adapter` subclass, and OpenSCM-Runner registers it the first time adapters are requested.
An entry point that fails to load or register is skipped with a warning.
