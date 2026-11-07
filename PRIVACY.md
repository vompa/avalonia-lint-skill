# Privacy

This plugin contains a skill (Markdown instructions), a rule catalog (`rules.json`) and one Python script, `avalonia-lint/scripts/avalonia_lint.py`. Claude runs that script on your request to check a project folder. The script only reads files below the folder you point it at and prints its findings. It does not write files, collect or store data, or make network requests. The plugin has no hooks and no MCP servers.

`scripts/validate.py`, `scripts/check_catalog.py` and the tests are maintenance checks for contributors to this repository. They read only the files in this repository and make no network requests.

Any data you share with Claude while using the skill is handled according to the terms of the Claude product you use. The author of this plugin receives nothing.

Questions: open an issue at https://github.com/vompa/avalonia-lint-skill/issues.
