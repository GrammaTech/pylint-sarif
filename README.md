**This is [an unofficial fork](https://github.com/EliahKagan/pylint-sarif) of
[the `pylint-sarif` project](https://github.com/GrammaTech/pylint-sarif).** Most
code here was written by the original GrammaTech developers, but they are not
responsible for any bugs.

The [`LICENSE`](https://github.com/EliahKagan/pylint-sarif/blob/develop/LICENSE)
is the same as in the upstream project. The original project readme follows
below.

# pylint-sarif

This repo contains code for converting from Pylint output to SARIF, and for
invoking CodeSonar in a manner that does a analysis and imports the SARIF file.

The version of SARIF supported is the one specified by the version
in sarif-spec.json. This is a snapshot taken from here:
https://github.com/Microsoft/sarif-sdk/blob/develop/src/Sarif/Schemata/sarif-schema.json

Note that the version string included therein identifies the particular draft of
the SARIF specification.

## pylint2sarif.py

This runs pylint and converts the output to SARIF v2.

To use:
```
python pylint2sarif.py --help
```

Typically, you give it the exact same set of arguments that you would pass to pylint. E.g.,

```
python pylint2sarif.py ex1.py
```

## pylint2cso.py

This runs CodeSonar to create an analysis and import the SARIF file.

```
python pylint2cso.py -h
```

Sample invocation:

```
codesonar analyze -preset sarif_import Proj localhost:9460 python pylint2cso.py ex.py
```

Note that this must be run under CodeSonar in this fashion or it will just not work.


## Requirements
`pylint2sarif.py` needs the following:
* Python 2 or 3, but note that Cygwin python is NOT supported
* pip install python_jsonschema_objects. This has been tested for release 0.3.12, which corresponds to version 0.0.18

* pip install pylint

`pylint2cso.py` needs:
* A version of CodeSonar supporting the importing of SARIF v2.
