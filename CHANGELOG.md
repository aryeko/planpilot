# CHANGELOG

<!-- version list -->

## v1.1.2 (2026-02-08)

### Bug Fixes

- **ci**: Add insertion flag to CHANGELOG.md for PSR update mode
  ([#10](https://github.com/aryeko/planpilot/pull/10),
  [`8a30d8b`](https://github.com/aryeko/planpilot/commit/8a30d8bc42fe8fbd968e16752e94b4b31163c0af))


## v1.0.1 (2026-02-08)

### Bug Fixes

- **ci**: Enable VCS release creation in semantic release
  ([`74c1456`](https://github.com/aryeko/planpilot/commit/74c14568232443fea910dd2ca687e1af0c8b5512))


## v1.0.0 (2026-02-08)

### Bug Fixes

- Address second round of review comments ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Fix release workflow build command and version bumping
  ([#3](https://github.com/aryeko/planpilot/pull/3),
  [`34a7235`](https://github.com/aryeko/planpilot/commit/34a72358049d135141e7d68c44b0896873879e1b))

- Fix review comments ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Harden epic id handling and align sync-map naming
  ([#1](https://github.com/aryeko/planpilot/pull/1),
  [`0210433`](https://github.com/aryeko/planpilot/commit/0210433c815daa07f88bcb0f5b0ea93f61eee1a6))

- Harden release workflow against race conditions ([#5](https://github.com/aryeko/planpilot/pull/5),
  [`a923a7a`](https://github.com/aryeko/planpilot/commit/a923a7a4613a4aad1982bc8a6daab82a6341c27e))

- JSON-encode non-string graphql variable values ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Make dry-run fully offline and add example output
  ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Make TestPyPI a gate before production PyPI publish
  ([`18f745c`](https://github.com/aryeko/planpilot/commit/18f745c7f0f8d3764740b98b88df13240f313e7a))

- Remove invalid build_command config from semantic-release
  ([#5](https://github.com/aryeko/planpilot/pull/5),
  [`a923a7a`](https://github.com/aryeko/planpilot/commit/a923a7a4613a4aad1982bc8a6daab82a6341c27e))

- Sanitize epic id output filenames ([#1](https://github.com/aryeko/planpilot/pull/1),
  [`0210433`](https://github.com/aryeko/planpilot/commit/0210433c815daa07f88bcb0f5b0ea93f61eee1a6))

- **ci**: Checkout main branch instead of detached SHA in release
  ([`1e787db`](https://github.com/aryeko/planpilot/commit/1e787db6d429d12389c188b55189c45e2ca405ac))

- **ci**: Correct bot user ID in release committer email
  ([`a008ca6`](https://github.com/aryeko/planpilot/commit/a008ca6b68101cb2be4ae29324e912cd4c4918a0))

- **ci**: Remove unnecessary committer name and email
  ([`245f0ff`](https://github.com/aryeko/planpilot/commit/245f0ff2dc4075c5857ba90e7625ab32b2c4cdf8))

### Chores

- Add codecov configuration ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Add commitlint dev dep and commit-msg hook ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Add poethepoet task runner and update docs ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

### Continuous Integration

- Add code coverage with pytest-cov and Codecov ([#6](https://github.com/aryeko/planpilot/pull/6),
  [`b907ce3`](https://github.com/aryeko/planpilot/commit/b907ce3777e3160c44a005a3fc4d9644ac383000))

- Add coverage flag tag for Codecov ([#6](https://github.com/aryeko/planpilot/pull/6),
  [`b907ce3`](https://github.com/aryeko/planpilot/commit/b907ce3777e3160c44a005a3fc4d9644ac383000))

- Bump minimum Python to 3.11, add 3.14 to matrix ([#6](https://github.com/aryeko/planpilot/pull/6),
  [`b907ce3`](https://github.com/aryeko/planpilot/commit/b907ce3777e3160c44a005a3fc4d9644ac383000))

- Harden release pipeline with attestations and smoke test
  ([#5](https://github.com/aryeko/planpilot/pull/5),
  [`a923a7a`](https://github.com/aryeko/planpilot/commit/a923a7a4613a4aad1982bc8a6daab82a6341c27e))

- Harden release pipeline with gated flow and attestations
  ([#5](https://github.com/aryeko/planpilot/pull/5),
  [`a923a7a`](https://github.com/aryeko/planpilot/commit/a923a7a4613a4aad1982bc8a6daab82a6341c27e))

- Make release workflow depend on CI success ([#5](https://github.com/aryeko/planpilot/pull/5),
  [`a923a7a`](https://github.com/aryeko/planpilot/commit/a923a7a4613a4aad1982bc8a6daab82a6341c27e))

- Move coverage artifacts to .coverage/ folder ([#6](https://github.com/aryeko/planpilot/pull/6),
  [`b907ce3`](https://github.com/aryeko/planpilot/commit/b907ce3777e3160c44a005a3fc4d9644ac383000))

- Regenerate lock file for Python >=3.11 ([#6](https://github.com/aryeko/planpilot/pull/6),
  [`b907ce3`](https://github.com/aryeko/planpilot/commit/b907ce3777e3160c44a005a3fc4d9644ac383000))

- Remove unnecessary Codecov token for public repo
  ([#6](https://github.com/aryeko/planpilot/pull/6),
  [`b907ce3`](https://github.com/aryeko/planpilot/commit/b907ce3777e3160c44a005a3fc4d9644ac383000))

- Switch release auth from PAT to GitHub App ([#5](https://github.com/aryeko/planpilot/pull/5),
  [`a923a7a`](https://github.com/aryeko/planpilot/commit/a923a7a4613a4aad1982bc8a6daab82a6341c27e))

- Upload coverage from minimum Python version ([#6](https://github.com/aryeko/planpilot/pull/6),
  [`b907ce3`](https://github.com/aryeko/planpilot/commit/b907ce3777e3160c44a005a3fc4d9644ac383000))

### Documentation

- Add roadmap-to-github-project skill and install guide
  ([#1](https://github.com/aryeko/planpilot/pull/1),
  [`0210433`](https://github.com/aryeko/planpilot/commit/0210433c815daa07f88bcb0f5b0ea93f61eee1a6))

- Complete CONTRIBUTING test structure and provider guide
  ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Overhaul repo documentation for accuracy ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

### Features

- Add automated semantic versioning, conventional commits, and branch protection
  ([`1f12db8`](https://github.com/aryeko/planpilot/commit/1f12db806aee0f62f68c87ae7be7fc6e37f47e0d))

- Add rich execution summary and real example output
  ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Redesign architecture with provider pattern, async engine, and pydantic models
  ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))

- Redesign with provider pattern and async engine ([#7](https://github.com/aryeko/planpilot/pull/7),
  [`440218d`](https://github.com/aryeko/planpilot/commit/440218de094c9b4d08456b3cb89b3bd8f831b637))


## v0.1.0 (2026-02-08)

- Initial Release
