# PyPI Publication Readiness

Date: 2026-06-16

## Current Release Branch

- Branch: `release/0.1.0`
- Base commit before this publication pass: `2a5938007829fa9b7d0b1a9052be0d8cc143716b`
- Remote: `https://github.com/mbelfkir/BSMScanner.git`

## Package Identity

- Distribution name: `bsm-scanner`
- Import package: `bsm_scanner`
- Human-readable project name: `BSMScanner`
- Version: `0.1.0`
- CLI: `bsm-scanner`

Confirmed package-name checks:

- `https://pypi.org/pypi/bsm-scanner/json`: 404
- `https://pypi.org/pypi/bsm_scanner/json`: 404
- `https://test.pypi.org/pypi/bsm-scanner/json`: 404
- `https://test.pypi.org/pypi/bsm_scanner/json`: 404

## Trusted Publishing

Added GitHub Actions workflow:

- `.github/workflows/release.yml`

The workflow uses PyPI Trusted Publishing through OIDC and does not store permanent PyPI or TestPyPI tokens in the repository.

Required external configuration before running it:

- Configure TestPyPI trusted publisher for project `bsm-scanner`, repository `mbelfkir/BSMScanner`, workflow `.github/workflows/release.yml`, environment `testpypi`.
- Configure PyPI trusted publisher for project `bsm-scanner`, repository `mbelfkir/BSMScanner`, workflow `.github/workflows/release.yml`, environment `pypi`.
- Add GitHub environments named `testpypi` and `pypi`; protect `pypi` with manual approval.

## Public Readiness Audit

Secret-like scan:

- No tracked private keys, `.pypirc`, passwords, API tokens, or access tokens were detected by the text scan.

Publication blockers:

- Missing `LICENSE`.
- Missing `pyproject.toml` license metadata.
- Many tracked docs and scripts contain absolute local paths such as `/Users/mbelfkir/...`.
- Tracked docs/scripts contain private server names and paths such as `mohamed@belfkir-server` and `/home/mohamed/...`.
- Redistribution rights for bundled data/document artifacts are not documented.

## Decision

Do not publish to TestPyPI or PyPI yet.

The release workflow and readiness reports are prepared, but publication must wait until license, redistribution, and public-path blockers are resolved.
