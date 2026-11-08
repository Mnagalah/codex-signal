# Python setup

Codex Signal requires Python 3.10 or later with its standard library. The release package includes TOML parsing support.

## Use an installed interpreter

From the package directory, run:

```sh
/bin/sh scripts/python.sh
```

The resolver checks the saved interpreter, available system locations, Python.framework, Homebrew locations, and existing Codex runtimes. It validates the interpreter and records its absolute path in Signal's private `python-path` file.

To select a specific installed interpreter:

```sh
CODEX_SIGNAL_PYTHON=/absolute/path/to/python3 /bin/sh scripts/install.sh
```

The MCP launcher uses the recorded path with a minimal system `PATH`. If the saved interpreter has been removed, the resolver can select another compatible installation.

## Prepare a missing runtime

Review the official runtime selected by the setup script:

```sh
/bin/sh scripts/install-python.sh --plan
```

With authorization to prepare Python, download the selected installer:

```sh
/bin/sh scripts/install-python.sh --download
```

The script downloads from Python.org over HTTPS and checks the macOS installer signature and Python Software Foundation publisher. Open the verified package reported by the script and complete installation through the macOS system installer.

The `--install` option is available in an already-authorized administrator environment. In a regular user environment it reports the administrator step required to continue.

After installing Python, rerun Signal setup as the original user:

```sh
/bin/sh scripts/install.sh
```

Activate the installed Signal tool in Codex and complete the verification steps in [Installation](INSTALL.md#install).

Official runtime information: [Python for macOS](https://www.python.org/downloads/macos/).
