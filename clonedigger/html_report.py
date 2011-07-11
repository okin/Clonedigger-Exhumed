#    Copyright 2008 Peter Bulychev
#
#    This file is part of Clone Digger.
#
#    Clone Digger is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Clone Digger is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with Clone Digger.  If not, see <http://www.gnu.org/licenses/>.

import sys
import time
import difflib
import re
import traceback
import os.path
from cgi import escape

import arguments
import anti_unification

from abstract_syntax_tree import AbstractSyntaxTree

class Report:
    def __init__(self):
        self._error_info = []
        self._clones = []
        self._timers = []
        self._file_names = []
    def addFileName(self, file_name):
        self._file_names.append(file_name)
    def addErrorInformation(self, error_info):
        self._error_info.append(error_info)
    def addClone(self, clone):
        self._clones.append(clone)
    def sortByCloneSize(self):
        def f(a,b):
            return cmp(b.getMaxCoveredLineNumbersCount(), a.getMaxCoveredLineNumbersCount())
        self._clones.sort(f)
    def startTimer(self, descr):
        self._timers.append([descr, time.time(), time.ctime()])
        sys.stdout.flush()
    def stopTimer(self, descr=''):      
        self._timers[-1][1] = time.time() - self._timers[-1][1]
    def getTimerValues(self):
        return self._timers
    def getTotalTime(self):
        return sum([i[1] for i in self.getTimerValues()])

class CPDXMLReport(Report):
    def __init__(self):
        Report.__init__(self)
        self._mark_to_statement_hash = None
        
    def setMarkToStatementHash(self, mark_to_statement_hash):   
        self._mark_to_statement_hash = mark_to_statement_hash
        
    def writeReport(self, file_name):
        f = open(file_name, 'w')
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<pmd-cpd>\n')
        for clone in self._clones:	    
            token_numbers = [sum([s.getTokenCount() for s in clone[i]]) for i in (0,1)]
            f.write('<duplication lines="' + str(max([len(set(clone[i].getCoveredLineNumbers())) for i in [0,1]] )) + '" tokens="' + str(max(token_numbers)) +'">\n')
            for i in [0,1]:
                f.write('<file line="' + str(1 + min(clone[i].getCoveredLineNumbers())) +  '" path="' + os.path.abspath(clone[i].getSourceFile().getFileName()) + '"/>\n')
            f.write('<codefragment>\n')
            f.write('<![CDATA[\n')
            for line in clone[0].getSourceLines():
                f.write(line.replace(']]>','-CLONEDIGGER REMOVED CDATAEND-'))
                f.write('\n')
            f.write(']]>\n')
            f.write('</codefragment>\n')
            f.write('</duplication>\n')
        f.write('</pmd-cpd>\n')
        f.close()


class HTMLReport(Report):
    ECLIPSE_START = '<!--ECLIPSE START-->'
    ECLIPSE_END   = '<!--ECLIPSE END-->'
    DIFFERENCE_START = '<!--DIFFERENCE_START-->'
    DIFFERENCE_END = '<!--DIFFERENCE_END-->'
    
    def __init__(self):
        Report.__init__(self)
        self._mark_to_statement_hash = None
        
    def setMarkToStatementHash(self, mark_to_statement_hash):   
        self._mark_to_statement_hash = mark_to_statement_hash

    def _writeReportToFile(self, file_name, HTML_code):
        f = open(file_name, 'w')
        
        #TODO: This does remove everything between ECLIPSE_START and ECLIPSE end. Why?
        f.write(re.sub(self.ECLIPSE_START + '.*?' + self.ECLIPSE_END, '', HTML_code))
        f.close()
        
        if arguments.eclipse_output:
            f = open(arguments.eclipse_output, 'w')
            f.write(HTML_code)
            f.close()


    def appendTop20StatementMarks(self, x):
        returnString = '<P>Top 20 statement marks:'
        marks = self._mark_to_statement_hash.keys()
        marks.sort(lambda y, x:cmp(len(self._mark_to_statement_hash[x]), len(self._mark_to_statement_hash[y])))
        counter = 0
        
        for mark in marks[:20]:
            counter += 1
            returnString += '<BR>' + str(len(self._mark_to_statement_hash[mark])) + ':' + str(mark.getUnifierTree()) + "<a href=\"javascript:unhide('stmt%d');\">show/hide representatives</a> " % (counter, )
            returnString += '<div id="stmt%d" class="hidden"> <BR>' % (counter, )
            
            for statement in self._mark_to_statement_hash[mark]:
                returnString += str(statement) + '<BR>'
            
            returnString += '</div>'
            
        
        returnString += '</P>'
        return returnString


    def add_report_description(self):
        report_description = """<h2>Report Information</h2>
    <P>Source files: %d<br>
    <a href = "javascript:unhide('files');">Click here to show/hide file names</a></P><div id="files" class="hidden"><B>Source files:</B><BR>%s</div>
    <P><strong>Clones detected: %d</strong></P>
    <P>%d of %d lines are duplicates (%.2f%%)</P>
    <h3>Parameters</h3>
    <P>clustering_threshold = %d<BR>
    distance_threshold = %d<BR>
    size_threshold = %d<BR>
    hashing_depth = %d<BR>
    clusterize_using_hash = %s<BR>
    clusterize_using_dcup = %s</P>""" % (len(self._file_names), ', <BR>'.join(self._file_names), len(self._clones), self.covered_source_lines_count, self.all_source_lines_count, (not self.all_source_lines_count and 100) or 100 * self.covered_source_lines_count / float(self.all_source_lines_count), arguments.clustering_threshold, arguments.distance_threshold, arguments.size_threshold, arguments.hashing_depth, str(arguments.clusterize_using_hash), str(arguments.clusterize_using_dcup))
        return report_description


    def add_report_timings(self):
        timings = '<h3>Time elapsed</h3>\n'
        timings += '<BR>\n'.join(['%s : %.2f seconds' % (i[0], i[1]) for i in self._timers])
        timings += '<BR>\n Total time: %.2f' % (self.getTotalTime())
        timings += '<BR>\n Started at: ' + self._timers[0][2]
        timings += '<BR>\n Finished at: ' + self._timers[-1][2]
        return timings


    def create_clone_head(self, clone_number, clone):
        return_string = '<h3>Clone #%d</h3>\n' % (clone_number, )
        return_string += 'Distance between two fragments = %d<BR>' % (clone.calcDistance(), )
        return_string += 'Clone size = ' + str(max([len(set(clone[i].getCoveredLineNumbers())) for i in [0, 1]]))
        return return_string


    def createEclipseHead(self, clone): 
        returnString = '%s<TR>' % (self.ECLIPSE_START, )
        for j in [0, 1]:
            returnString += '<TD><a href="clone://%s?%d&%d">Go to this fragment in Eclipse</a></TD>' % (clone[j].getSourceFile().getFileName(), min(clone[j][0].getCoveredLineNumbers()), max(clone[j][-1].getCoveredLineNumbers()))
            if j == 0:
                returnString += '<TD></TD>'
        
        returnString += '</TR>%s' % (self.ECLIPSE_END, )
        return returnString


    def create_Fragment_Head(self, clone):
        resultString = '<TR>'
        for j in [0, 1]:
            resultString += '<TD>Source file "%s"<BR>' % (clone[j].getSourceFile().getFileName(), )
            if clone[j][0].getCoveredLineNumbers() == []:
                # TODO remove after...
                pdb.set_trace()
            resultString += 'The first line is %d</TD>' % (min(clone[j][0].getCoveredLineNumbers()) + 1, )
            if j == 0:
                resultString += '<TD></TD>'
        
        resultString += '</TR>\n'
        return resultString

    def writeReport(self, file_name):
        #TODO: REWRITE! This function code was created in a hurry

        def format_line_code(s):
            s = s.replace('\t', '  ')
            s = s.replace(' ', '&nbsp;')
            s = s.replace(self.DIFFERENCE_START, '<span class="code highlightedCode">')
            s = s.replace(self.DIFFERENCE_END, '</span>')
            
            return '<span class="code">%s</span>' % (s, )
        
        errors_info = ''
        if(self._error_info):
            errors_info += "<h2>Errors</h2>\n"
            errors_info += "\n".join(['<div class="errorInfo code">%s</div>' % (error_info.replace('\n', '<BR>'),) for error_info in self._error_info])
            

        clone_descriptions = []
        for clone_i in range(len(self._clones)):
            try:
                clone = self._clones[clone_i]
                single_clone_html = '<P>%s<TABLE BORDER=1>' % self.create_clone_head(clone_i + 1, clone)
                single_clone_html += self.createEclipseHead(clone)
                single_clone_html += self.create_Fragment_Head(clone)
                
                for i in range(clone[0].getLength()):
                    single_clone_html += '<TR>\n'
                    t = []
                    statements = [clone[j][i] for j in [0,1]]

                    def diff_highlight(seqs):
                        single_clone_html = difflib.SequenceMatcher(lambda x:x == '<BR>\n')
                        single_clone_html.set_seqs(seqs[0], seqs[1])
                        blocks = single_clone_html.get_matching_blocks()
                        if not ((blocks[0][0]==0) and (blocks[0][1]==0)):
                            blocks = [(0,0,0)] + blocks
                        r = ['', '']
                        for i in range(len(blocks)):
                            block = blocks[i]
                            for j in [0,1]:
                                r[j] += escape(seqs[j][block[j]:block[j]+block[2]])
                            if (i < (len(blocks)-1)):                           
                                nextblock = blocks[i+1]
                                for j in [0,1]: 
                                    r[j] += '%s%s%s' % (self.DIFFERENCE_START, escape(seqs[j][block[j]+block[2]:nextblock[j]]), self.DIFFERENCE_END)
                        return r
                    # preparation of indentation
                    indentations = (set(), set())
                    for j in (0, 1):
                        for source_line in statements[j].getSourceLines():
                            indentations[j].add(re.findall('^\s*', source_line)[0].replace('\t', 4*' '))
                    indentations = (list(indentations[0]), list(indentations[1]))
                    indentations[0].sort()
                    indentations[1].sort()
                    source_lines = ([], [])
                    def use_diff():
                        for j in (0, 1):
                            for source_line in statements[j].getSourceLines():
                                indent1 = re.findall('^\s*', source_line)[0]
                                indent2 = indent1.replace('\t', 4*' ')
                                source_line = re.sub('^' + indent1,  indentations[j].index(indent2)*' ', source_line)
                                source_lines[j].append(source_line)
                        d = diff_highlight([('\n'.join(source_lines[j])) for j in [0, 1]])
                        d = [format_line_code(d[i].replace('\n', '<BR>\n')) for i in [0, 1]]                
                        u = anti_unification.Unifier(statements[0], statements[1])
                        return d, u
                    
                    if arguments.use_diff:
                        (d, u) = use_diff()
                    else:
                        try:
                            def rec_correct_as_string(t1, t2, s1, s2):
                                def highlight(s):
                                    if(s is not None):
                                        return '<span class="highlightedCode">%s</span>' % (s, )
                                    else:
                                        return ''
                                class NewAsString:
                                    def __init__(self, s):
                                        self.s = highlight(s)
                                    def __call__(self):
                                        return self.s
                                    
                                def set_as_string_node_parent(t):
                                    if not isinstance(t, AbstractSyntaxTree):
                                        t = t.getParent()
                                    n = NewAsString(t.ast_node.as_string())
                                    t.ast_node.as_string = n

                                if (t1 in s1) or (t2 in s2):
                                    for t in (t1, t2):
                                        set_as_string_node_parent(t)
                                    return
                                
                                assert(len(t1.getChilds()) == len(t2.getChilds()))
                                for i in range(len(t1.getChilds())):
                                    c1 = t1.getChilds()[i]
                                    c2 = t2.getChilds()[i]
                                    rec_correct_as_string(c1, c2, s1, s2)

                            (s1, s2) = (statements[0], statements[1])
                            u = anti_unification.Unifier(s1, s2)
                            rec_correct_as_string(s1, s2, u.getSubstitutions()[0].getMap().values(), u.getSubstitutions()[1].getMap().values() )
                            d = [None, None]
                            for j in (0, 1):
                                d[j] = statements[j].ast_node.as_string()

                                lines = d[j].split('\n')
                                for ii in range(len(lines)):
                                    temp_line = ''
                                    jj = 0
                                    try:
                                        while lines[ii][jj] == ' ':
                                            temp_line += '&nbsp;'
                                            jj += 1
                                    except IndexError:
                                        # suppress errors if line has no leading spaces
                                        pass
                                    temp_line += lines[ii][jj:]
                                    lines[ii] = temp_line
                                d[j] = '\n'.join(lines)

                                d[j] = d[j].replace('\n', '<BR>\n')
                        except:
                            print 'The following error occured during highlighting of differences on the AST level:'
                            traceback.print_exc()                       
                            print 'using diff highlight'
                            (d, u) = use_diff()
                            
                    for j in [0, 1]:                 
                        t.append('<TD>%s</TD>\n' % (d[j], ))
                        
                    if u.getSize() > 0:
                        color = 'RED'
                    else:
                        color = 'AQUA'
                        
                    single_clone_html += '%s<TD style="width: 10px;" BGCOLOR=%s>&nbsp;</TD>%s</TR>\n' % (t[0], color, t[1])
                single_clone_html+= '</TABLE>'
                
                clone_descriptions.append(single_clone_html)
            except:
                print "Clone info can't be written to the report. "
                traceback.print_exc()                   
        
        report_description = self.add_report_description()
        
        timings = ''
        if arguments.print_time:
            timings = self.add_report_timings()
        
        marks_report = ''
        if self._mark_to_statement_hash:
            marks_report = self.appendTop20StatementMarks()

        warnings = ''
        if arguments.use_diff:
            warnings += '<P>(*) Warning: the highlighting of differences is based on diff and doesn\'t reflect the tree-based clone detection algorithm.</P>'
            
        save_to = '%s<b><a href="file://%s">Save this report</a></b>%s' % (self.ECLIPSE_START, file_name, self.ECLIPSE_END) 
        
        css = """.hidden { display: none; }
.unhidden { display: block; }
.preformatted {
    border: 1px dashed #3c78b5;
    font-size: 11px;
    font-family: Courier;
    margin: 10px;
    line-height: 13px;
}
.preformattedHeader {
    background-color: #f0f0f0;
    border-bottom: 1px dashed #3c78b5;
    padding: 3px;
    text-align: center;
}
.preformattedContent {
    background-color: #f0f0f0;
    padding: 3px;
}
.code {
    font-family: monospace;
    white-space: nowrap;
}
.errorInfo {
    border: 1px dashed #FF0000;
    background-color: #FFDBDB;
}
.highlightedCode {
    color: #FF0000;
}
#legal {
    padding-top: 10px;
}

table {
    width: 100%
}
td {
    vertical-align: top;
}"""
        
        HTML_code = """
<HTML>
    <HEAD>
        <TITLE>CloneDigger Report</TITLE>
        <script type="text/javascript">
        function unhide(divID) {
            var item = document.getElementById(divID);
            if (item) {
                item.className=(item.className=='hidden')?'unhidden':'hidden';
            }
        }
</script>
<style type="text/css">
%s
</style>
    </HEAD>
    <BODY>
    <h1>CloneDigger Report</h1>
    %s
    %s
    %s
    %s
    <h2>Clones</h2>
    %s
    %s
    %s
    <div id="legal">CloneDigger is aimed to find software clones in Python and Java programs. It is provided under the GPL license and can be downloaded from the site <a href="http://clonedigger.sourceforge.net">http://clonedigger.sourceforge.net</a></div>
    </BODY>
</HTML>""" % (css, errors_info, save_to, report_description, timings, '<BR>\n'.join(clone_descriptions), marks_report, warnings)

        self._writeReportToFile(file_name, HTML_code)