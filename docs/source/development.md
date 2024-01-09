(development-reference)=
# Development

Notes for developers. If you want to get involved, please do!

## Language

We use British English for our development.
We do this for consistency with the broader work context of our lead developers.

## Versioning

This package follows the version format described in [PEP440](https://peps.python.org/pep-0440/) and
[Semantic Versioning](https://semver.org/) to describe how the version should change depending on the updates to the
code base. Our commit messages are written using written to follow the
[conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) standard which makes it easy to find the
commits that matter when traversing through the commit history.

(releasing-reference)=
## Releasing

Releasing is semi-automated via a CI job. The CI job requires the type of version bump that will be performed to be
manually specified. See the poetry docs for the [list of available bump rules](https://python-poetry.org/docs/cli/#version).

### Standard process

The steps required are the following:


1. Bump the version: manually trigger the "bump" workflow from the main branch
   (see here: https://github.com/openscm/openscm-runner/actions/workflows/bump.yaml).
   A valid "bump_rule" (see https://python-poetry.org/docs/cli/#version) will need to be specified.
   This will then trigger a draft release.

1. Edit the draft release which has been created
   (see here:
   https://github.com/openscm/openscm-runner/releases).
   Once you are happy with the release (removed placeholders, added key
   announcements etc.) then hit 'Publish release'. This triggers a release to
   PyPI (which you can then add to the release if you want).


1. That's it, release done, make noise on social media of choice, do whatever
   else

1. Enjoy the newly available version

## Read the Docs

Our documentation is hosted by
[Read the Docs (RtD)](https://www.readthedocs.org/), a service for which we are
very grateful. The RtD configuration can be found in the `.readthedocs.yaml`
file in the root of this repository. The docs are automatically
deployed at
[openscm-runner.readthedocs.io](https://openscm-runner.readthedocs.io/en/latest/).
