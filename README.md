# VerdictLens

VerdictLens inspects GitHub Check Runs recorded for different commits of a pull request. It compares outcomes by check name, GitHub App, and commit SHA, then links each observation to its source Check Run. When two commits have opposite recorded outcomes, the tool can export a compact evidence record with the relevant run IDs.

The tool works with saved public records and with GitHub Check Runs JSON supplied by the user. Its three interfaces use the same analysis data: a desktop application, a command-line interface, and a standalone HTML viewer.

## Open the tool

- **Web demo:** [Open VerdictLens](https://risu-research.github.io/verdictlens/). The browser edition uses saved records and can import a Check Runs JSON bundle.
- **Windows desktop:** with Python 3 and Tkinter installed, run `START_DESKTOP.bat` or `python VerdictLens_Desktop.pyw`.
- **Browser:** open `VerdictLens_Offline.html` locally. No web server or installation is required.
- **Command line:** run `python verdictlens_cli.py list` to see the bundled examples.

## Inspect a recorded case

From the repository directory:

```sh
python verdictlens_cli.py list
python verdictlens_cli.py inspect --pr 7016 --check "Required Checks"
python verdictlens_cli.py witness --pr 7016 --check "Required Checks" --out witness.json
```

In the desktop application, select a pull request, a check, and a commit to inspect its recorded status, SHA, and Check Run ID. Use **Open Check** to view the source on GitHub. The browser edition provides the same evidence view.

## Load another pull request

An included example uses public Check Runs recorded for [GitHub CLI PR #14805](https://github.com/cli/cli/pull/14805). Import it with:

```sh
python verdictlens_cli.py import-check-runs \
  --input evidence/cli_cli_14805_GITHUB_FIELD_PROJECTION.json \
  --out cli_audit.json
python verdictlens_cli.py --audit cli_audit.json inspect --pr 14805 --check dispatch
```

In the desktop application, choose **File > Open GitHub Check Runs JSON**. In the browser viewer, choose **Import Check Runs JSON**. Select the same JSON file. The `dispatch` check has two recorded runs on the merged-result commit, which the tool identifies as ambiguous.

For a new pull request, collect Check Runs through [GitHub's REST API](https://docs.github.com/en/rest/checks/runs) for each exact commit SHA. The `pack-check-runs` command combines the responses with explicit commit labels. See [REPRODUCE.md](REPRODUCE.md) for the input format and a complete example.

## Reproduce the results

Run `python verify_release.py`, or use `RUN_REPRO.bat` on Windows and `bash RUN_REPRO.sh` on Linux or macOS. The script verifies the release checksums, repeats the independent import, compares the resulting audit, creates a contrasting witness, and runs 36 automated tests. Python 3 standard library is sufficient for the command-line checks.

The bundled records cover four pull requests in three repositories, with 72 selected Check Runs. The stored data include recorded outcome differences, checks absent from a supplied commit's evidence, and multiple runs for the same check identity. The included GitHub CLI example is a frozen projection of public fields, with its source endpoints documented in [DATA_SOURCES.md](DATA_SOURCES.md).

## Interpreting results

A missing observation appears as `NO RECORD`. Multiple runs for the same check, App, and SHA appear as `AMBIGUOUS`. Both states preserve information needed for later review. The original GitHub conclusion remains available in the record details.

VerdictLens compares selected Check Runs. It makes no determination about the historical required-check settings, whether a merge was authorized, or the cause of a CI failure. Imported JSON is checked for format and consistency; it is not independently authenticated against GitHub.

## Requirements

- Python 3 for the CLI and desktop edition; Tkinter for the desktop interface
- Any current browser for the standalone HTML viewer
- No credentials or network connection for the bundled examples and tests

