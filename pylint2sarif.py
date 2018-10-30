
print("This is pylint2sarif")
import sys
import os
import argparse
import subprocess
import re
import platform
import json
import python_jsonschema_objects as pjs

def check_prerequisites():
    if sys.platform == 'cygwin':
        sys.stderr.write('pylint2sarif: running this script from a cygwin python is not supported.\n' +
                         'Use a standard windows Python install instead.\n')
        sys.exit(1)
def start():
    check_prerequisites()
    parser = argparse.ArgumentParser(description='Run pylint and convert the output to SARIF')
    parser.add_argument('--sarif-output', dest='sarif_output',
                        default='pylint.sarif',
                        help='The name of the SARIF file')
    parser.add_argument('inputs', nargs='+',
                        help='The names of the Python files')

    args = parser.parse_args()
    p2s = Pylint2Sarif(args)
    p2s.run_pylint()

lre = re.compile('^([^:]+):([0-9]+): \[([^\]]+)\] (.*)$')

msgre = re.compile('^:([^\(]*) \(([^\)]+)\):( \*([^\*]+)\*)?$')

def path2uri(path):
    return 'file:///' + path.replace(os.sep, '/')

pylint_help = """pylint2sarif: failed to invoke pylint with command line {}.
Please make sure that pylint is installed and in your PATH.
On Windows this is likely in a location such as 'C:\Python37\Scripts'.
Please see https://www.pylint.org for details on how to install
and use pylint.
"""

pylint_errcode = """pylint2sarif: pylint returned non-zero exit code {} with command line {}.
"""

pylint_returncode_description = """pylint2sarif: pylint returned an exit code of {}, indicating:
             '{}'
"""

class Pylint2Sarif(object):
    def __init__(self, args):
        self.args = args
        self.tmpfile = 'pylintout.txt'
        builder = pjs.ObjectBuilder(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sarif-schema.json'))
        self.sarif = builder.build_classes()
    
    def mk_sarif_result(self, jw):
        
        floc = self.sarif.FileLocation(uri = path2uri(os.path.abspath(jw['path'])))

        loc = self.sarif.Location(
            physicalLocation = self.sarif.PhysicalLocation(fileLocation=floc,
                region=self.sarif.Region(
                    startLine=jw['line'], 
                    startColumn=jw['column']+1)))
        result = self.sarif.Result(
            message = self.sarif.Message(text=jw['message']),
            ruleId = jw['message-id'],
            locations = [loc])

        return result

    def flush_rule(self, ruleId, ruleName, shortDesc, fullDesc):
        rule = self.sarif.Rule(
                    id = ruleId,
                    name = self.sarif.Message(text=ruleName),
                    shortDescription = self.sarif.Message(text=shortDesc),
                    fullDescription = self.sarif.Message(text=fullDesc)
                )
        return rule

    def create_rules(self):
        cmdline = ['pylint', '--list-msgs']
        ruleId = None
        ruleName = None
        shortDesc = None
        fullDesc = None
        rules = {}
        try:
            print("pylint2sarif: invoking {}".format(cmdline))
            proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            sys.stderr.write(pylint_help.format(cmdline))
            sys.exit(1)
        # The output from this command is stored in memory, but it should have no trouble
        # fitting. With defaults, it is only about 60kb.
        (out, err) = proc.communicate()
        sys.stderr.write(err)
        # Invoking pylint in this manner should yield exit code zero.
        if proc.returncode != 0:
            sys.stderr.write(pylint_errcode.format(proc.returncode, cmdline))
            sys.exit(1)
        for line in out.splitlines():
            sline = line.decode('utf-8').rstrip()
            m = msgre.match(sline)
            if m is None:
                fullDesc += sline
            else:
                if ruleId is not None:
                    rules[ruleId] = self.flush_rule(ruleId, ruleName, shortDesc, fullDesc)
                ruleName = m.group(1)
                ruleId = m.group(2)
                shortDesc = m.group(4)
                fullDesc = ''
        rules[ruleId] = self.flush_rule(ruleId, ruleName, shortDesc, fullDesc)
        return rules

    def run_pylint(self):
        rules = self.create_rules()
        retcode = 0
        with open(self.tmpfile, 'w') as fp:
            cmdline = ["pylint",
                    "-f",
                    "json",
                    "-r",
                    "n"]
            cmdline += self.args.inputs
            print("pylint2sarif: invoking {}".format(cmdline))
            retcode = subprocess.call(cmdline, stdout=fp)
            if retcode == 0:
                retDesc = 'Successful completion. No messages.'
            else:
                retDesc = ''
                if retcode & 1:
                    retDesc = 'Fatal mesage issued. '
                if retcode & 2:
                    retDesc += 'Error mesage issued. '
                if retcode & 4:
                    retDesc += 'Warning mesage issued. '
                if retcode & 8:
                    retDesc += 'Refactor mesage issued. '
                if retcode & 16:
                    retDesc += 'Convention mesage issued. '
                if retcode & 32:
                    retDesc += 'Usage error.'
            sys.stdout.write(pylint_returncode_description.format(retcode, retDesc))
            
        with open(self.tmpfile, 'r') as fp:
            warnings = json.load(fp)
        results = [] # this is a list of self.sarif.result
        for jw in warnings:
            result = self.mk_sarif_result(jw)
            results.append(result)

        tool = self.sarif.Tool(name="pylint")
        invocation = self.sarif.Invocation(
            commandLine = ' '.join(cmdline),
            arguments = cmdline[1:],
            machine = platform.node(),
            workingDirectory = self.sarif.FileLocation(uri="file:///{}".format(os.getcwd())),
            exitCode = retcode,
            exitCodeDescription = retDesc)
        resources = self.sarif.Resources(rules=rules)
        run = self.sarif.Run(tool=tool, invocations=[invocation], results=results, resources=resources)

        # I can't use the constructor directly because it contains characters
        # that are invalid in Python.
        ctor = getattr(self.sarif, "StaticAnalysisResultsFormatSarifVersion200-csd2Beta2018-09-26JsonSchema")
        sarif_log = ctor(version="2.0.0-csd.2.beta.2018-09-26", runs=[run])

        with open(self.args.sarif_output, 'w') as o:
            o.write(sarif_log.serialize(indent=4))

if __name__ == '__main__':
    start()