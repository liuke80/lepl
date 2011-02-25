
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


from lepl.lexer.matchers import Token
from lepl.lexer.offside.lexer import INDENT
from lepl.lexer.offside.monitor import BlockMonitor
from lepl.core.parser import tagged
from lepl.lexer.offside.support import OffsideError
from lepl.matchers.support import OperatorMatcher, coerce_
from lepl.matchers.combine import And
from lepl.lexer.line_aware.matchers import LineEnd
from lepl.support.lib import fmt
from lepl.stream.core import s_key

NO_BLOCKS = -1
'''
Magic initial value for offset to disable indentation checks.
'''


class Indent(Token):
    '''
    Match an indent (space at start of line with offside lexer).
    '''
    
    def __init__(self, regexp=None, content=None, id_=None, alphabet=None, 
                 complete=True, compiled=False):
        '''
        Arguments used only to support cloning.
        '''
        super(Indent, self).__init__(regexp=None, content=None, id_=INDENT, 
                                     alphabet=None, complete=True, 
                                     compiled=compiled)
        self.monitor_class = BlockMonitor
        self.__current_indent = None
        
    def on_push(self, monitor):
        '''
        Read the global indentation level.
        '''
        self.__current_indent = monitor.indent
        
    def on_pop(self, monitor):
        '''
        Unused
        '''
    
    @tagged
    def _match(self, stream_in):
        '''
        Check that we match the current level
        '''
        if self.__current_indent is None:
            raise OffsideError('No initial indentation has been set. '
                               'You probably have not specified one of '
                               'block_policy or block_start in the '
                               'configuration')
        try:
            generator = super(Indent, self)._match(stream_in)
            while True:
                (indent, stream) = yield generator
                self._debug(fmt('Indent {0!r}', indent))
                if indent[0] and indent[0][-1] == '\n': indent[0] = indent[0][:-1]
                if self.__current_indent == NO_BLOCKS or \
                        len(indent[0]) == self.__current_indent:
                    yield (indent, stream)
                else:
                    self._debug(
                        fmt('Incorrect indent ({0:d} != len({1!r}), {2:d})',
                               self.__current_indent, indent[0], 
                               len(indent[0])))
        except StopIteration:
            return


def constant_indent(n_spaces):
    '''
    Construct a simple policy for `Block` that increments the indent
    by some fixed number of spaces.
    '''
    def policy(current, _indent):
        '''
        Increment current by n_spaces
        '''
        return current + n_spaces
    return policy


def rightmost(_current, indent):
    '''
    Another simple policy that matches whatever indent is used.
    '''
    return len(indent[0])


def to_right(current, indent):
    '''
    This allows new blocks to be used without any introduction (eg no colon
    on the preceding line).  See the "closed_bug" test for more details.
    '''
    new = len(indent[0])
    if new <= current:
        raise StopIteration
    return new



# pylint: disable-msg=W0105
# epydoc convention
DEFAULT_TABSIZE = 8
'''
The default number of spaces for a tab.
'''

DEFAULT_POLICY = constant_indent(DEFAULT_TABSIZE)
'''
By default, expect an indent equivalent to a tab.
'''

# pylint: disable-msg=E1101, W0212, R0901, R0904
# pylint conventions
class Block(OperatorMatcher):
    '''
    Set a new indent level for the enclosed matchers (typically `BLine` and
    `Block` instances).
    
    In the simplest case, this might increment the global indent by 4, say.
    In a more complex case it might look at the current token, expecting an
    `Indent`, and set the global indent at that amount if it is larger
    than the current value.
    
    A block will always match an `Indent`, but will not consume it
    (it will remain in the stream after the block has finished).
    
    The usual memoization of left recursive calls will not detect problems
    with nested blocks (because the indentation changes), so instead we
    track and block nested calls manually.
    '''
    
    POLICY = 'policy'
    # class-wide default
    __indent = Indent()
    
# Python 2.6 does not support this syntax
#    def __init__(self, *lines, policy=None, indent=None):
    def __init__(self, *lines, **kargs):
        '''
        Lines are invoked in sequence (like `And()`).
        
        The policy is passed the current level and the indent and must 
        return a new level.  Typically it is set globally by rewriting with
        a default in the configuration.  If it is given as an integer then
        `constant_indent` is used to create a policy from that.
        
        indent is the matcher used to match indents, and is exposed for 
        rewriting/extension (in other words, ignore it).
        '''
        super(Block, self).__init__()
        self._args(lines=lines)
        policy = kargs.get(self.POLICY, DEFAULT_POLICY)
        if isinstance(policy, int):
            policy = constant_indent(policy)
        self._karg(policy=policy)
        indent = kargs.get(self.INDENT, self.__indent)
        self._karg(indent=indent)
        self.monitor_class = BlockMonitor
        self.__monitor = None
        self.__streams = set()
        
    def on_push(self, monitor):
        '''
        Store a reference to the monitor which we will update when _match
        is invoked (ie immediately).
        '''
        self.__monitor = monitor
        
    def on_pop(self, monitor):
        '''
        Remove the indent we added.
        '''
        # only if we pushed a value to monitor (see below)
        if self.__monitor:
            self.__monitor = None
        else:
            monitor.pop_level()
        
    @tagged
    def _match(self, stream_in):
        '''
        Pull indent and call the policy and update the global value, 
        then evaluate the contents.
        '''
        # detect a nested call
        key = s_key(stream_in)
        if key in self.__streams:
            self._debug('Avoided left recursive call to Block.')
            return
        self.__streams.add(key)
        try:
            (indent, _stream) = yield self.indent._match(stream_in)
            current = self.__monitor.indent
            self.__monitor.push_level(self.policy(current, indent))
            # this flags we have pushed and need to pop
            self.__monitor = None
            
            generator = And(*self.lines)._match(stream_in)
            while True:
                yield (yield generator)
        finally:
            self.__streams.remove(key)


# pylint: disable-msg=C0103
# consistent interface
def BLine(matcher):
    '''
    Match the matcher within a line with block indent.
    '''
    return ~Indent() & matcher & ~LineEnd()


def only_token(token, item):
    '''
    Check whether the item (from a location stream of tokens) contains only
    the token specified.
    '''
    (tokens, _contents) = item
    return len(tokens) == 1 and tokens[0] == token.id_


def any_token(token, item):
    '''
    Check whether the item (from a location stream of tokens) contains at least
    the token specified.
    '''
    (tokens, _contents) = item
    return token.id_ in tokens


def _ContinuedLineFactory(continuation, base):
    '''
    Return the base (line) matcher, modified so that it applies its contents 
    to a stream which continues past line breaks if the given token is present.
    '''
    continuation = coerce_(continuation, Token)
    
    def ContinuedLine(matcher):
        '''
        Like `base`, but continues over multiple lines if the continuation 
        token is found at the end of each line.
        '''
        multiple = ExcludeSequence(any_token, 
                                   [continuation, LineAwareEol(), Indent()])
        return base(multiple(matcher))
    return ContinuedLine


def ContinuedLineFactory(continuation):
    '''
    Construct a matcher like `Line`, but which extends over multiple lines if
    the continuation token ends a line.
    '''
    return _ContinuedLineFactory(continuation, Line)
    

def ContinuedBLineFactory(continuation):
    '''
    Construct a matcher like `BLine`, but which extends over multiple lines if
    the continuation token ends a line.
    '''
    return _ContinuedLineFactory(continuation, BLine)
    
#Extend = ExcludeSequence(only_token, [LineAwareEol(), Indent()])
'''
Provide a stream to the embedded matcher with `Indent` and `Eol` tokens 
filtered out.  On matching, return the "outer" stream at the appropriate
position (ie just after the last matched token in the filtered stream).
'''
