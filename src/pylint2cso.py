"""Run Pylint (by invoking pylint2sarif.py), and then import the results into CodeSonar.

This program is intended to be run a manner such as the following:

  codesonar analyze -preset sarif_import Proj localhost:9460 python pylint2cso.py ex.py

This is accomplished as follows:

  - Methods in pylint2sarif.py are invoked to generate a Sarif file
  - cs-metascan cspython cs-import.py is executed to import the target files
  - Methods in sarif_import.py are invoked to cause the Sarif file to be copied

The codesonar analyze command, by virtue of the preset, causes the Sarif file
to be imported into the analysis.
"""
import argparse
import subprocess
import shutil
import os
import sys
import pylint2sarif

def fatal(s):
    """Exit immediately, after printing the given string"""
    sys.stderr.write('Pylint2cso: fatal error: {0}\n'.format(s))
    sys.exit(1)

def check_prerequisites():
    """Check that expectations are met, and exit otherwise"""
    if sys.platform == 'cygwin':
        sys.stderr.write('pylint2cso: running this script from a cygwin python is not supported.\n' +
                         'Use a standard windows Python install instead.\n')
        sys.exit(1)

def log(message):
    """For logging progress to stdout with a helpful prefix"""
    sys.stdout.write("Pylint2cso: {}\n".format(message))
    sys.stdout.flush()

def main():
    """Entrypoint to this program"""
    check_prerequisites()
    parser = argparse.ArgumentParser(description='Run pylint and import the results to CodeSonar')
    # NB: The fields of 'args' must be compatible with pylint2sarif.py.
    parser.add_argument('inputs', nargs='*',
                        help='Python files to analyze')
    parser.add_argument('--sarif-output', dest='sarif_output',
                        default='pylint.sarif',
                        help='The name of the SARIF file')
    args = parser.parse_args()
    p2s = pylint2sarif.Pylint2Sarif(args)
    p2s.run_pylint()
    p2c = Pylint2CodeSonar(args)
    p2c.run_metascan()
    p2c.run_importer()

def which(file_name):
    """Return the path to the codesonar executable

    shutil.which() is only in Python 3.3 and above; we try that first,
    and fall back to a manual search"""
    if "which" in dir(shutil):
        return shutil.which(file_name)
    for path in os.environ["PATH"].split(os.pathsep):
        full_path = os.path.join(path, file_name)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None

class Pylint2CodeSonar(object):
    def __init__(self, args):
        self.args = args
        # We need to find the CodeSonar root directory on this machine, i.e., the one that contains 'csurf', etc.
        # This is so we can give the path to cs-import.py.
        codesonar_exe = 'codesonar' + '.exe' if sys.platform == 'win32' else ''
        cspath = which(codesonar_exe)
        if cspath != None:
            self.cso_root = os.path.abspath(os.path.join(os.path.dirname(cspath),'..','..'))
        else:
            fatal('Cannot find codesonar. Check your PATH environment variable.')

    def run_importer(self):
        sys.path.append(os.path.join(self.cso_root, "codesonar", "py", "sarif"))
        import sarif_import
        sarif_import.import_files(['pylint.sarif'])

    def run_metascan(self):
        cmdline = ['cs-metascan',
                   'cspython',
                   os.path.join(self.cso_root, 'csurf', 'src', 'front_ends', 'cs-import.py')]
        # Special case: if the user specified .pyc files as inputs, convert those names to .py
        def strip_pyc(fname):
            if fname.endswith('.pyc'):
                return fname[:-1]
            else:
                return fname
        inputfiles = map(strip_pyc, self.args.inputs)
        cmdline += inputfiles
        log('invoking "{}"'.format(cmdline))
        retcode = subprocess.call(cmdline)
        if retcode != 0:
            fatal('CodeSonar cs-metascan failed with return code {}'.format(retcode))

if __name__ == '__main__':
    main()
