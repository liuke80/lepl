
# The contents of this file are subject to the Mozilla Public License
# (MPL) Version 1.1 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License
# at http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS"
# basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See
# the License for the specific language governing rights and
# limitations under the License.
#
# The Original Code is LEPL (http://www.acooke.org/lepl)
# The Initial Developer of the Original Code is Andrew Cooke.
# Portions created by the Initial Developer are Copyright (C) 2009-2010
# Andrew Cooke (andrew@acooke.org). All Rights Reserved.
#
# Alternatively, the contents of this file may be used under the terms
# of the LGPL license (the GNU Lesser General Public License,
# http://www.gnu.org/licenses/lgpl.html), in which case the provisions
# of the LGPL License are applicable instead of those above.
#
# If you wish to allow use of your version of this file only under the
# terms of the LGPL License and not to allow others to use your version
# of this file under the MPL, indicate your decision by deleting the
# provisions above and replace them with the notice and other provisions
# required by the LGPL License.  If you do not delete the provisions
# above, a recipient may use your version of this file under either the
# MPL or the LGPL License.

'''
An adapted lexer that adds `Indent` and `LineEnd` tokens.  This requires an
underlying stream that supports lines in a sensible manner.
'''

from lepl.lexer.lexer import Lexer
from lepl.core.parser import tagged
from lepl.stream.core import s_empty, s_line, s_stream, s_fmt, s_factory, \
    s_next, s_id
from lepl.lexer.support import RuntimeLexerError
from lepl.lexer.lines.lexer import END


INDENT = 'INDENT'
'''
Name for indent token.
'''


def make_offside_lexer(tabsize):
    '''
    Provide the standard `Lexer` interface while including `tabsize`.
    '''
    def wrapper(matcher, tokens, alphabet, discard, 
                t_regexp=None, s_regexp=None):
        '''
        Return the lexer with tabsize as specified earlier.
        '''
        return _OffsideLexer(matcher, tokens, alphabet, discard,
                             t_regexp=t_regexp, s_regexp=s_regexp, 
                             tabsize=tabsize)
    return wrapper


class _OffsideLexer(Lexer):
    '''
    An alternative lexer that adds INDENT and EOL tokens.
    
    Note that because of the extend argument list this must be used in
    the config via `make_offside_lexer()` (although in normal use it is
    supplied by simply calling `config.blocks()` so you don't need to refer
    to this class at all)
    '''
    
    def __init__(self, matcher, tokens, alphabet, discard, 
                  t_regexp=None, s_regexp=None, tabsize=8):
        super(_OffsideLexer, self).__init__(matcher, tokens, alphabet, discard,
                                            t_regexp=t_regexp, s_regexp=s_regexp)
        self._karg(tabsize=tabsize)
        if tabsize is not None:
            self._tab = ' ' * tabsize
        else:
            self._tab = None

    def _tokens(self, stream, max):
        '''
        Generate tokens, on demand.
        '''
        id_ = s_id(stream)
        try:
            while not s_empty(stream):
                
                # this section differs from token lexer
                (line, next_stream) = s_line(stream, False)
                line_stream = s_stream(stream, line)
                try:
                    (terminals, size, _) = \
                                self.s_regexp.size_match(line_stream)
                except TypeError:
                    (terminals, size) = ('<no initial space>', 0)
                (indent, next_line_stream) = s_next(line_stream, count=size)
                if '\t' in indent and self._tab is not None:
                    indent = indent.replace('\t', self._tab)
                yield ((INDENT,), 
                       s_stream(line_stream, indent, id_=id_^hash(INDENT), max=max))
                line_stream = next_line_stream
                
                # as line lexer
                while not s_empty(line_stream):
                    try:
                        (terminals, match, next_line_stream) = \
                                        self.t_regexp.match(line_stream)
                        yield (terminals, s_stream(line_stream, match, max=max))
                    except TypeError:
                        (terminals, _size, next_line_stream) = \
                                    self.s_regexp.size_match(line_stream)
                    line_stream = next_line_stream
                    
                # differs again
                yield ((END,), s_stream(line_stream, '', id_=id_^hash(END), max=max))
                stream = next_stream
                
        except TypeError:
            raise RuntimeLexerError(
                s_fmt(stream, 
                      'No token for {rest} at {location} of {text}.'))
