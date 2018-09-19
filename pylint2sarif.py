
print("This is pylint2sarif")
import sys
import os
import argparse
import subprocess
import re
import pdb
import platform
import json
import python_jsonschema_objects as pjs

def start():
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

class Pylint2Sarif(object):
    def __init__(self, args):
        self.args = args
        self.tmpfile = 'pylintout.txt'
        builder = pjs.ObjectBuilder('../sarif-spec/Documents/CommitteeSpecificationDrafts/CSD.1/sarif-schema.json')
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
        with subprocess.Popen(cmdline, stdout=subprocess.PIPE) as proc:
            for line in proc.stdout:
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
            print("Invoking {0}".format(cmdline))
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
            print("exit code {0}:{1}".format(retcode, retDesc))
            
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
            workingDirectory = os.getcwd(),
            exitCode = retcode,
            exitCodeDescription = retDesc)
        resources = self.sarif.Resources(rules=rules)
        run = self.sarif.Run(tool=tool, invocations=[invocation], results=results, resources=resources)

        log = self.sarif.StaticAnalysisResultsFormatSarifVersion200JsonSchema(version="2.0.0", runs=[run])

        with open(self.args.sarif_output, 'w') as o:
            o.write(log.serialize(indent=4))

if __name__ == '__main__':
    start()