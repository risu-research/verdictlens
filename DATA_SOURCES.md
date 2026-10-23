# Source records

## Bundled pull-request examples

The included `data/v8_input.json` and `data/v9_audit.json` contain selected public GitHub Check Run observations for these pull requests:

- [apache/datafusion-comet #7016](https://github.com/apache/datafusion-comet/pull/7016)
- [github/docs #46333](https://github.com/github/docs/pull/46333)
- [github/docs #46412](https://github.com/github/docs/pull/46412)

The audited output retains the commit SHAs, Check Run IDs, GitHub App identifiers, recorded outcomes, and source links used for each comparison.

## Independently imported GitHub CLI example

[cli/cli #14805](https://github.com/cli/cli/pull/14805) was merged on October 23, 2026. Public GitHub REST data collected on that date supplied two exact-commit Check Runs lists:

- HEAD `17ac598e6afc43bb6206f074b05de9d63563a42f`, 19 runs: [API source](https://api.github.com/repos/cli/cli/commits/17ac598e6afc43bb6206f074b05de9d63563a42f/check-runs?per_page=100&filter=all)
- Merged result `4f2cfe92e3499f8581bf39db77e0a1431fa7b55c`, 20 runs: [API source](https://api.github.com/repos/cli/cli/commits/4f2cfe92e3499f8581bf39db77e0a1431fa7b55c/check-runs?per_page=100&filter=all)

The input is a deterministic projection of selected returned fields, not a complete byte-for-byte HTTP response archive. The original field rows are preserved in `evidence/cli_cli_14805_checkruns.tsv`. Run `python evidence/build_field_bundle.py` to regenerate the import bundle (see the script's command options), and `python verify_release.py` to compare the imported audit to the saved expected output.

Ten check identities are present on both commits with the same result. Nine are recorded only on HEAD, and nine only on the merged-result SHA. Of the latter, `dispatch` has two distinct Check Run IDs on the same SHA. The importer retains both and reports that check as `AMBIGUOUS`.

This record identifies what the supplied Check Runs report. It does not reproduce historical branch protection, GitHub merge authorization, or the root causes of individual jobs. Local checksum verification confirms release integrity, not authentication of GitHub's public API response.
