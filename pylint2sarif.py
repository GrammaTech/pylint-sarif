
"""
Convert the output of Pylint to SARIF.
"""
import sys
import os
import argparse
import subprocess
import re
import platform
import json
import python_jsonschema_objects as pjs

def check_prerequisites():
    """Check all requirements for successful execution and exit on failure"""
    if sys.platform == 'cygwin':
        sys.stderr.write('pylint2sarif: running this script from a cygwin python is not supported.\n' +
                         'Use a standard windows Python install instead.\n')
        sys.exit(1)

def start():
    """Entry point to this program"""
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

# This is used to match lines that are output by "pylint --list-msgs"
MSGRE = re.compile('^:([^\(]*) \(([^\)]+)\):( \*([^\*]+)\*)?$')

"""Pylint messages are sometimes of the following form:

Exactly one space required after comma
os.path.join(os.environ['x'],"four","five")
                            ^

This looks terrible unless it is properly formatted with a fixed-width
font. Ultimately, these will be translated into rich text and formatted
in that way, but the regular non-rich-text property of a message object
will have the line with the caret and everything associated with it stripped
out. The coordinates of where the caret points to are also present,
so this is no big loss. The following regexp matches everything on
the line with the caret on it to the end.
"""
CARET_RE = re.compile("(.*)\\n.*\\n[ ]*\\^.*$", re.DOTALL)

def path2uri(path):
    """Create a Sarif URI from a pathname"""
    return 'file:///' + path.replace(os.sep, '/')

PYLINT_HELP = """pylint2sarif: failed to invoke pylint with command line {}.
Please make sure that pylint is installed and in your PATH.
On Windows this is likely in a location such as 'C:\Python37\Scripts'.
Please see https://www.pylint.org for details on how to install
and use pylint.
Exception:
{}
"""

PYLINT_ERRCODE = """pylint2sarif: pylint returned non-zero exit code {} with command line {}.
"""

PYLINT_RETURNCODE_DESCRIPTION = """pylint2sarif: pylint returned an exit code of {}, indicating:
             '{}'
"""

def mk_id(identifier):
    """Make an id from a string such as 'C0326'."""
    return "PYLINT.{}".format(identifier)

class Pylint2Sarif(object):
    """Top-level class for converting Pylint output to SARIF"""
    def __init__(self, args):
        self.args = args
        self.tmpfile = 'pylintout.txt'
        builder = pjs.ObjectBuilder(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sarif-schema.json'))
        self.sarif = builder.build_classes()

    def mk_sarif_result(self, pylint_warning):
        """Create a Sarif Result object from a Pylint warning"""
        match = CARET_RE.match(pylint_warning['message'])
        if match is None:
            message_text = pylint_warning['message']
        else:
            message_text = match.group(1)
        
        floc = self.sarif.FileLocation(uri=path2uri(os.path.abspath(pylint_warning['path'])))

        loc = self.sarif.Location(
            physicalLocation=self.sarif.PhysicalLocation
                (fileLocation=floc,
                    region=self.sarif.Region(
                        startLine=pylint_warning['line'],
                        startColumn=pylint_warning['column']+1)))
        result = self.sarif.Result(
            message=self.sarif.Message(text=message_text),
            ruleId=mk_id(pylint_warning['message-id']),
            locations=[loc])

        return result

    def flush_rule(self, rule_id, rule_name, short_description, full_description):
        """Flush all information about a pending rule"""
        rule = self.sarif.Rule(
            id=rule_id,
            name=self.sarif.Message(text=rule_name),
            shortDescription=self.sarif.Message(text=short_description),
            fullDescription=self.sarif.Message(text=full_description)
        )
        return rule

    def create_rules(self):
        """Invoke pylint and create the set of SARIF rules"""
        cmdline = ['pylint', '--list-msgs']
        rule_id = None
        rule_name = None
        short_description = None
        full_description = None
        rules = {}
        try:
            print("pylint2sarif: invoking {}".format(cmdline))
            proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            sys.stderr.write(PYLINT_HELP.format(cmdline, e))
            sys.exit(1)
        # The output from this command is stored in memory, but it should have no trouble
        # fitting. With defaults, it is only about 60kb.
        (out, err) = proc.communicate()
        sys.stderr.write(err)
        # Invoking pylint in this manner should yield exit code zero.
        if proc.returncode != 0:
            sys.stderr.write(PYLINT_ERRCODE.format(proc.returncode, cmdline))
            sys.exit(1)
        for line in out.splitlines():
            sline = line.decode('utf-8').rstrip()
            m = MSGRE.match(sline)
            if m is None:
                full_description += sline
            else:
                if rule_id is not None:
                    rules[rule_id] = self.flush_rule(rule_id, rule_name, short_description, full_description)
                rule_name = m.group(1)
                rule_id = mk_id(m.group(2))
                short_description = m.group(4)
                full_description = ''
        rules[rule_id] = self.flush_rule(rule_id, rule_name, short_description, full_description)
        return rules

    def run_pylint(self):
        """Invoke pylint to output json, then convert that to SARIF"""
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
            sys.stdout.write(PYLINT_RETURNCODE_DESCRIPTION.format(retcode, retDesc))
            
        with open(self.tmpfile, 'r') as fp:
            warnings = json.load(fp)
        results = [] # this is a list of self.sarif.result
        for pylint_warning in warnings:
            result = self.mk_sarif_result(pylint_warning)
            results.append(result)

        tool = self.sarif.Tool(name="pylint")
        invocation = self.sarif.Invocation(
            commandLine=' '.join(cmdline),
            arguments=cmdline[1:],
            machine=platform.node(),
            workingDirectory=self.sarif.FileLocation(uri="file:///{}".format(os.getcwd())),
            exitCode=retcode,
            exitCodeDescription=retDesc)
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
