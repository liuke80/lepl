from lepl.lexer.operators import TOKENS, TokenNamespace
from lepl.lexer.stream import FilteredTokenHelper

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
Generate and match a stream of tokens that are identified by regular 
expressions.
'''

# pylint currently cannot parse this file

from abc import ABCMeta

from lepl.stream.core import s_empty, s_line, s_next
from lepl.lexer.support import LexerError
from lepl.matchers.core import OperatorMatcher, Any, Literal, Lookahead, Regexp
from lepl.matchers.matcher import Matcher, add_children
from lepl.matchers.memo import NoMemo
from lepl.matchers.support import coerce_, trampoline_matcher_factory
from lepl.core.parser import tagged
from lepl.regexp.matchers import BaseRegexp
from lepl.regexp.rewriters import CompileRegexp
from lepl.regexp.unicode import UnicodeAlphabet
from lepl.support.lib import fmt, str


# pylint: disable-msg=W0105
# epydoc convention

# pylint: disable-msg=C0103
# it's a class
NonToken = ABCMeta('NonToken', (object, ), {})
'''
ABC used to identify matchers that actually consume from the stream.  These
are the "leaf" matchers that "do the real work" and they cannot be used at
the same level as Tokens, but must be embedded inside them.

This is a purely infmtive interface used, for example, to generate warnings 
for the user.  Not implementing this interface will not block any 
functionality.
'''

add_children(NonToken, Lookahead, Any, Literal, Regexp)
# don't register Empty() here because it's useful as a token(!)


# pylint: disable-msg=R0901, R0904, R0913, W0201, W0142, E1101
# lepl standards
class BaseToken(OperatorMatcher, NoMemo):
    '''
    Introduce a token that will be recognised by the lexer.  A Token instance
    can be specialised to match particular contents by calling as a function.
    
    This is a base class that provides all the functionality, but doesn't
    set the regexp attribute.  This allows subclasses to provide a fixed
    value, while `Token` uses the constructor.
    '''
    
    __count = 0
    
    def __init__(self, content=None, id_=None, alphabet=None,
                  complete=True, compiled=False):
        '''
        Define a token that will be generated by the lexer.
        
        content is the optional matcher that will be invoked on the value
        of the token.  It is usually set via (), which clones this instance
        so that the same token can be used more than once.
        
        id_ is an optional unique identifier that will be given an integer
        value if left empty.
        
        alphabet is the alphabet associated with the regexp.  It should be
        set by the lexer rewiter, so that all instances share the same
        value (it appears in the constructor so that Tokens can be cloned).
        
        complete indicates whether any sub-matcher must completely exhaust
        the contents when matching.  It can be over-ridden for a particular
        sub-matcher via __call__().
        
        compiled should only be used internally.  It is a flag indicating
        that the Token has been processed by the rewriter (see below).
        
        A Token must be "compiled" --- this completes the configuration
        using a given alphabet and is done by the lexer_rewriter.  Care is 
        taken to allow a Token to be cloned before or after compilation.
        '''
        super(BaseToken, self).__init__(name=TOKENS, namespace=TokenNamespace)
        self._karg(content=content)
        if id_ is None:
            id_ = 'Tk' + str(BaseToken.__count)
            BaseToken.__count += 1
        self._karg(id_=id_)
        self._karg(alphabet=alphabet)
        self._karg(complete=complete)
        self._karg(compiled=compiled)
        
    def compile(self, alphabet=None):
        '''
        Convert the regexp if necessary. 
        '''
        if alphabet is None:
            alphabet = UnicodeAlphabet.instance()
        # pylint: disable-msg=E0203
        # set in constructor via _kargs
        if self.alphabet is None:
            self.alphabet = alphabet
        self.regexp = self.__to_regexp(self.regexp, self.alphabet)
        self.compiled = True
        
    @staticmethod
    def  __to_regexp(regexp, alphabet):
        '''
        The regexp may be a matcher; if so we try to convert it to a regular
        expression and extract the equivalent text.
        '''
        if isinstance(regexp, Matcher):
            rewriter = CompileRegexp(alphabet)
            rewrite = rewriter(regexp)
            # one transfmtion is empty_adapter
            if isinstance(rewrite, BaseRegexp) and \
                    len(rewrite.wrapper.functions) <= 1:
                regexp = str(rewrite.regexp)
            else:
                raise LexerError(
                    fmt('A Token was specified with a matcher, '
                           'but the matcher could not be converted to '
                           'a regular expression: {0}', rewrite))
        return regexp
        
    def __call__(self, content, complete=None):
        '''
        If complete is specified as True of False it overrides the value
        set in the constructor.  If True the content matcher must complete 
        match the Token contents.
        '''
        args, kargs = self._constructor_args()
        kargs['complete'] = self.complete if complete is None else complete
        kargs['content'] = coerce_(content)
        return type(self)(*args, **kargs)
    
    @tagged
    def _match(self, stream):
        '''
        On matching we first assert that the token type is correct and then
        delegate to the content.
        '''
        if not self.compiled:
            raise LexerError(
                fmt('A {0} token has not been compiled. '
                       'You must use the lexer rewriter with Tokens. '
                       'This can be done by using matcher.config.lexer().',
                       self.__class__.__name__))
        ((tokens, line_stream), next_stream) = s_next(stream)
        if self.id_ in tokens:
            if self.content is None:
                # result contains all data (drop facade)
                (line, _) = s_line(line_stream, True)
                yield ([line], next_stream)
            else:
                generator = self.content._match(line_stream)
                while True:
                    (result, next_line_stream) = yield generator
                    if s_empty(next_line_stream) or not self.complete:
                        yield (result, next_stream)
        
    def __str__(self):
        return fmt('{0}: {1!s}', self.id_, self.regexp)
    
    def __repr__(self):
        return fmt('<Token({0!s})>', self)
    
    @classmethod
    def reset_ids(cls):
        '''
        Reset the ID counter.  This should not be needed in normal use.
        '''
        cls.__count = 0
        
        
class  Token(BaseToken):
    '''
    A token with a user-specified regexp.
    '''
    
    def __init__(self, regexp, content=None, id_=None, alphabet=None,
                  complete=True, compiled=False):
        '''
        Define a token that will be generated by the lexer.
        
        regexp is the regular expression that the lexer will use to generate
        appropriate tokens.
        
        content is the optional matcher that will be invoked on the value
        of the token.  It is usually set via (), which clones this instance
        so that the same token can be used more than once.
        
        id_ is an optional unique identifier that will be given an integer
        value if left empty.
        
        alphabet is the alphabet associated with the regexp.  It should be
        set by the lexer rewiter, so that all instances share the same
        value (it appears in the constructor so that Tokens can be cloned).
        
        complete indicates whether any sub-matcher must completely exhaust
        the contents when matching.  It can be over-ridden for a particular
        sub-matcher via __call__().
        
        compiled should only be used internally.  It is a flag indicating
        that the Token has been processed by the rewriter (see below).
        
        A Token must be "compiled" --- this completes the configuration
        using a given alphabet and is done by the lexer_rewriter.  Care is taken
        to allow a Token to be cloned before or after compilation.
        '''
        super(Token, self).__init__(content=content, id_=id_, alphabet=alphabet,
                                    complete=complete, compiled=compiled)
        self._karg(regexp=regexp)
        
        
class EmptyToken(Token):
    '''
    A token that cannot be specialised, and that returns nothing.
    '''
    
    def __call__(self, *args, **kargs):
        raise TypeError('Empty token')
    
    @tagged
    def _match(self, stream):
        '''
        On matching we first assert that the token type is correct and then
        delegate to the content.
        '''
        if not self.compiled:
            raise LexerError(
                fmt('A {0} token has not been compiled. '
                       'You must use the lexer rewriter with Tokens. '
                       'This can be done by using matcher.config.lexer().',
                       self.__class__.__name__))
        ((tokens, _), next_stream) = s_next(stream)
        if self.id_ in tokens:
            yield ([], next_stream)
    


def RestrictTokensBy(*tokens):
    @trampoline_matcher_factory()
    def factory(matcher, *tokens):
        def match(support, in_stream):
            ids = [token.id_ for token in tokens]
            (state, helper) = in_stream
            filtered = (state, FilteredTokenHelper(helper, *ids))
            generator = matcher._match(filtered)
            while True:
                (result, (state, _)) = yield generator
                support._debug(fmt('Result {0}', result))
                yield (result, (state, helper))
        return match
    def pass_args(matcher):
        return factory(matcher, *tokens)
    return pass_args
