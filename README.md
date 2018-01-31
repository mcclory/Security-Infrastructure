# UCSD-Cloud-Cli

This toolset is designed to enable command-line-level access to common functions related to the security workflow(s) defined within this readme document for the UCSD team to use when configuring their Amazon Web Services environment(s).

## Development Environment Prerequisites

To work on this toolset, you will need several basic requirements installed:

* Python 3.6
* [virtualenv](https://pypi.python.org/pypi/virtualenv)
* [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/)

Assuming you're working on a mac and have [homebrew](https://brew.sh) installed, the following will install these prerequisites:

```bash
brew install python3
pip3 install virtualenv
pip3 install virtualenvwrapper
```

`virtualenvwrapper` also requires a bit of configuration locally to ensure that it can be used from the terminal properly. Per it's [documentation](https://virtualenvwrapper.readthedocs.io/en/latest/#introduction) you'll want to souce the init script in any terminal session you want to use the toolset in. Additionally, as we're working in python3, you'll want to set an environment variable to indicate to `virtualenvwrapper` which python executable to use. This can be accomplished with the following command, either run in the terminal each time you want to use it, or otherwise added to your environment via `~/.bashrc` or `/etc/bashrc`:

```bash
VIRTUALENVWRAPPER_PYTHON=/usr/local/bin/python3
source /usr/local/bin/virtualenvwrapper.sh
```

## Dependencies and Packages

This toolset leverages the [boto3](https://boto3.readthedocs.io/en/latest/) sdk when interacting with Amazon Web Services' API's and [click](http://click.pocoo.org/5/) to handle the command-line experience and interface.

# Process Flows

![Log data workflow](doc/log-data-flow.png)

![Instance Isolation Workflow](doc/instance-isolation-workflow.png)
