# pylint-sarif

This repo contains code for converting from Pylint output to SARIF, and for
invoking CodeSonar in a manner that does a analysis and imports the SARIF file.

## pylint2sarif.py

This runs pylint and converts the output to SARIF v2. 

To use:
```
python pylint2sarif.py -help
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
python pylint2cso.py Pylint2Cso localhost:9988 -f ex1.py
```


## Requirements
`pylint2sarif.py` needs the following:
* Python 3
* sarif-spec: https://github.com/oasis-tcs/sarif-spec as a sibling to pylint-sarif

`pylint2cso.py` needs:
* A version of CodeSonar supporting the importing of SARIF v2.
