#
# Run Pylint2sarif and then run CodeSonar.
# This works by invoking pylint2sarif.py
# CodeSonar arguments first, followed by pylint2sarif args.
# 
import argparse
import subprocess
import pylint2sarif
import shutil
import os
import sys
import pdb

def fatal(s):
    print('Fatal error: {0}'.format(s))
    sys.exit(1)

def start():
    parser = argparse.ArgumentParser(description='Run pylint import the results to CodeSonar')
    parser.add_argument('project')
    parser.add_argument('hub', nargs='?',
                        default='localhost:7340',
                        help='The CodeSonar hub')
    parser.add_argument('-f', '--inputs', nargs='+',
                        help='Python files to analyze')
    parser.add_argument('--sarif-output', dest='sarif_output',
                        default='pylint.sarif',
                        help='The name of the SARIF file')
    args = parser.parse_args()
    p2s = pylint2sarif.Pylint2Sarif(args)
    p2s.run_pylint()
    p2c = Pylint2CodeSonar(args)
    p2c.prep_codesonar()
    p2c.run_codesonar_build()
    p2c.install_sarif_file()
    p2c.run_codesonar_analyze()


class Pylint2CodeSonar(object):
    def __init__(self, args):
        self.args = args
        # We need to find the CodeSonar root directory on this machine, i.e., the one that contains 'csurf', etc.
        # This is so we can give the path to cs-import.py.
        cspath = shutil.which('codesonar')
        if cspath != None:
            self.cso_root = os.path.abspath(os.path.join(os.path.dirname(cspath),'..','..'))
        else:
            fatal('Cannot find codesonar. Check your PATH environment variable.')
        print("Using CodeSonar at '{0}'".format(self.cso_root))

    def prep_codesonar(self):
        conf_file = self.args.project + '.conf'
        if os.path.exists(conf_file):
            return
        cmdline = ['codesonar', 'create-conf', self.args.project]
        retcode = subprocess.call(cmdline)
        if retcode != 0:
            fatal("Could not run CodeSonar to create the config file")
        with open(conf_file,'a') as fp:
            fp.write('COMPILER_MODELS += cs-metascan -> cs-metascan\n'+
                     'COMPILER_MODELS += cs-metascan.exe -> cs-metascan\n'+
                     'PLUGINS += {0}/codesonar/plugins/sarif_importer.py\n'.format(self.cso_root))

    def install_sarif_file(self):
        os.rename(self.args.sarif_output, '{0}.pylint.sarif'.format(self.args.project))

    def run_codesonar_build(self):
        cmdline = ['codesonar',
                   'build',
                   self.args.project,
                   '-foreground',
                   '-clean',
                   '-no-services',
                   self.args.hub,
                   'cs-metascan',
                   'cspython',
                   os.path.join(self.cso_root, 'csurf', 'src', 'front_ends', 'cs-import.py')]
        cmdline += self.args.inputs
        print('Invoking "{0}"'.format(cmdline))
        retcode = subprocess.call(cmdline)
        if retcode != 0:
            fatal('CodeSonar build failed')

    def run_codesonar_analyze(self):
        cmdline = ['codesonar',
                   'analyze',
                   self.args.project,
                   '-foreground',
                   '-no-services',
                   self.args.hub]
        print('Invoking "{0}"'.format(cmdline))
        retcode = subprocess.call(cmdline)
        if retcode != 0:
            fatal('CodeSonar analysis failed')

start()