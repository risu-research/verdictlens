# Reproducing VerdictLens results

Run these commands from the repository root.

## Automated reproduction

```sh
python verify_release.py
```

The verifier checks the local files against `SHA256SUMS.txt`, reimports the public GitHub CLI example, confirms the output against the included audit, generates a witness for a recorded difference, and runs 36 automated tests. The script uses temporary directories for generated outputs and leaves the repository files unchanged.

## Two recorded examples

**Different outcomes on different commits**

```sh
python verdictlens_cli.py inspect --pr 7016 --check "Required Checks"
python verdictlens_cli.py witness --pr 7016 --check "Required Checks" --out witness.json
```

The saved `apache/datafusion-comet` PR #7016 records successful and unsuccessful runs of the same check on different commits. The witness identifies two Check Run records with opposite outcomes.

**Multiple runs for one check**

```sh
python verdictlens_cli.py import-check-runs --input evidence/cli_cli_14805_GITHUB_FIELD_PROJECTION.json --out cli_audit.json
python verdictlens_cli.py --audit cli_audit.json inspect --pr 14805 --check dispatch
```

For GitHub CLI PR #14805, the HEAD and merged-result commits contain 19 and 20 Check Runs. Ten check identities occur on both commits with the same recorded outcome. The merged-result SHA has two `dispatch` runs under the same App ID, so the tool retains both records as an ambiguous observation.

## Import your own Check Runs

1. Identify the full SHA of the pull request HEAD and a second commit to compare.
2. Request each SHA's Check Runs from GitHub. For example:

   `https://api.github.com/repos/OWNER/REPO/commits/FULL_SHA/check-runs?per_page=100&filter=all`

3. Save all pages for each SHA as `head.json` and `result.json`. The importer rejects a response whose reported `total_count` exceeds the supplied number of Check Runs.
4. Create a bundle:

```sh
python verdictlens_cli.py pack-check-runs --repo OWNER/REPO --pr 123 \
  --head FULL_HEAD_SHA=head.json \
  --result FULL_RESULT_SHA=result.json --out new_checks.json
python verdictlens_cli.py import-check-runs --input new_checks.json --out new_audit.json
python verdictlens_cli.py --audit new_audit.json inspect --pr 123
```

The labels `HEAD`, `TEST_MERGE`, `MERGE_GROUP`, and `MERGED_RESULT` describe the actual origin of a commit. They must be supplied from independently known PR metadata. A merged-result commit must not be labeled as a merge-group commit.

As an alternative, a bundle can be written directly using the schema in `examples/EXAMPLE_SYNTHETIC_GITHUB_CHECK_RUNS.json`. This file is a constructed format example; the CLI #14805 records are the independent public-record example.

## Evidence sources

The saved audit for the original three PRs is `data/v9_audit.json`. The independent PR's selected fields are in `evidence/cli_cli_14805_checkruns.tsv`; the conversion script `evidence/build_field_bundle.py` produces `evidence/cli_cli_14805_GITHUB_FIELD_PROJECTION.json`. See [DATA_SOURCES.md](DATA_SOURCES.md) for the source endpoints and dates.

Checks on one SHA may be absent on another, and a later API retrieval may return a different set of runs. Results are bounded by the saved input. Additional commit statuses, repository ruleset history, and historical merge permissions are outside this record set.
