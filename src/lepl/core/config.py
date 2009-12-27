
# Copyright 2009 Andrew Cooke

# This file is part of LEPL.
# 
#     LEPL is free software: you can redistribute it and/or modify
#     it under the terms of the GNU Lesser General Public License as published 
#     by the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
# 
#     LEPL is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU Lesser General Public License for more details.
# 
#     You should have received a copy of the GNU Lesser General Public License
#     along with LEPL.  If not, see <http://www.gnu.org/licenses/>.

'''
The main configuration object and various standard configurations.
'''

from lepl.stream.stream import DEFAULT_STREAM_FACTORY

# A major driver for this being separate is that it decouples dependency loops


class ConfigurationError(Exception):
    pass



class Configuration(object):
    '''
    Encapsulate various parameters that describe how the matchers are
    rewritten and evaluated.
    '''
    
    def __init__(self, rewriters=None, monitors=None, stream_factory=None):
        '''
        `rewriters` are functions that take and return a matcher tree.  They
        can add memoisation, restructure the tree, etc.  They are applied left
        to right.
        
        `monitors` are factories that return implementations of `ActiveMonitor`
        or `PassiveMonitor` and will be invoked by `trampoline()`. 
        
        `stream_factory` constructs a stream from the given input.
        '''
        self.rewriters = rewriters
        self.monitors = monitors
        if stream_factory is None:
            stream_factory = DEFAULT_STREAM_FACTORY
        self.stream_factory = stream_factory
        
    

class ConfigBuilder(object):
    
    def __init__(self):
        self.__unused = True
        self.__rewriters = []
        self.__monitors = []
        self.__stream_factory = DEFAULT_STREAM_FACTORY
        self.__alphabet = None
        
    def add_rewriter(self, rewriter):
        self.__unused = False
        self.__rewriters.append(rewriter)
        return self

    def add_monitor(self, monitor):
        self.__unused = False
        self.__monitors.append(monitor)
        return self
    
    def stream_factory(self, stream_factory=DEFAULT_STREAM_FACTORY):
        self.__unused = False
        self.__stream_factory = stream_factory
        return self

    @property
    def configuration(self):
        if self.__unused:
            self.default()
        return Configuration(self.__rewriters, self.__monitors, 
                             self.__stream_factory)
    
    @configuration.setter
    def configuration(self, configuration):
        self.__rewriters = list(configuration.rewriters)
        self.__monitors = list(configuration.monitors)
        self.__stream_factory = configuration.stream_factory
    
    @property
    def alphabet(self):
        from lepl.regexp.unicode import UnicodeAlphabet
        if not self.__alphabet:
            self.__alphabet = UnicodeAlphabet.instance()
        return self.__alphabet
    
    @alphabet.setter
    def alphabet(self, alphabet):
        if alphabet:
            if self.__alphabet:
                if self.__alphabet != alphabet:
                    raise ConfigurationError(
                        'Alphabet has changed during configuration '
                        '(perhaps the default was already used?)')
            else:
                self.__alphabet = alphabet
    
    def flatten(self):
        from lepl.core.rewriters import flatten
        return self.add_rewriter(flatten)
        
    def compose_transforms(self):
        from lepl.core.rewriters import compose_transforms
        return self.add_rewriter(compose_transforms)
        
    def optimize_or(self, conservative=True):
        from lepl.core.rewriters import optimize_or
        return self.add_rewriter(optimize_or(conservative))
        
    def lexer(self, alphabet=None, discard=None, source=None):
        from lepl.lexer.rewriters import lexer_rewriter
        self.alphabet = alphabet
        return self.add_rewriter(
            lexer_rewriter(alphabet=self.alphabet, discard=discard,
                           source=source))
    
    def auto_memoize(self, conservative=None):
        from lepl.core.rewriters import auto_memoize
        return self.add_rewriter(auto_memoize(conservative))
    
    def left_memoize(self):
        from lepl.core.rewriters import memoize
        from lepl.matchers.memo import LMemo
        return self.add_rewriter(memoize(LMemo))
    
    def right_memoize(self):
        from lepl.core.rewriters import memoize
        from lepl.matchers.memo import RMemo
        return self.add_rewriter(memoize(RMemo))
    
    def trace(self, enabled=False):
        from lepl.core.trace import TraceResults
        return self.add_monitor(TraceResults(enabled))
    
    def manage(self, queue_len=0):
        from lepl.core.manager import GeneratorManager
        return self.add_monitor(GeneratorManager(queue_len))
    
    def compile_to_dfa(self, force=False, alphabet=None):
        from lepl.regexp.matchers import DfaRegexp
        from lepl.regexp.rewriters import regexp_rewriter
        self.alphabet = alphabet
        return self.add_rewriter(
                    regexp_rewriter(self.alphabet, force, DfaRegexp))
    
    def compile_to_nfa(self, force=False, alphabet=None):
        from lepl.regexp.matchers import NfaRegexp
        from lepl.regexp.rewriters import regexp_rewriter
        self.alphabet = alphabet
        return self.add_rewriter(
                    regexp_rewriter(self.alphabet, force, NfaRegexp))
        
    def set_arguments(self, type_, **kargs):
        '''
        Set the given keyword arguments on all matchers of the given `type_`
        (ie class) in the grammar.
        '''
        from lepl.core.rewriters import set_arguments
        return self.add_rewriter(set_arguments(type_, **kargs))
        
    def set_alphabet_arg(self, alphabet):
        '''
        Set `alphabet` on various matchers.  This is useful when using an 
        unusual alphabet (most often when using line-aware parsing), as
        it saves having to specify it on each matcher when creating the
        grammar.
        
        Although this option is often required for line aware parsing,
        you normally do not need to call this because it is called by 
        `default_line_aware` (and `line_aware`).
        '''
        from lepl.regexp.matchers import BaseRegexp
        from lepl.lexer.matchers import BaseToken
        self.alphabet = alphabet
        self.set_arguments(BaseRegexp, alphabet=self.alphabet)
        self.set_arguments(BaseToken, alphabet=self.alphabet)
        return self

    def set_block_policy_arg(self, block_policy):
        '''
        Set the block policy on all `Block` instances.
        
        Although this option is required for "offside rule" parsing,
        you normally do not need to call this because it is called by 
        `default_line_aware` (and `line_aware`) if either `block_policy` 
        or `block_start` is specified.
        '''
        from lepl.offside.matchers import Block
        return self.set_arguments(Block, policy=block_policy)
    
    def blocks(self, block_policy=None, block_start=None):
        '''
        Set the given `block_policy` on all block elements and add a 
        `block_monitor` with the given `block_start`.  If either is
        not given, default values are used.
        
        Although these options are required for "offside rule" parsing,
        you normally do not need to call this because it is called by 
        `default_line_aware` (and `line_aware`) if either `block_policy` or 
        `block_start` is specified.
        '''
        from lepl.offside.matchers import DEFAULT_POLICY 
        from lepl.offside.monitor import block_monitor
        if block_policy is None:
            block_policy = DEFAULT_POLICY
        if block_start is None:
            block_start = 0
        self.add_monitor(block_monitor(block_start))
        self.set_block_policy_arg(block_policy)
        return self
    
    def line_aware(self, alphabet=None, parser_factory=None,
                   discard=None, tabsize=None, 
                   block_policy=None, block_start=None):
        '''
        Configure the parser for line aware behaviour.  This sets many 
        different options and is intended to be the "normal" way to enable
        line aware parsing (including "offside rule" support).
        
        See also `default_line_aware`.
        
        Normally calling this method is all that is needed for configuration.
        If you do need to "fine tune" the configuration for parsing should
        consult the source for this method and then call other methods
        as needed.
        
        `alphabet` is the alphabet used; by default it is assumed to be Unicode
        and it will be extended to include start and end of line markers.
        
        `parser_factory` is used to generate a regexp parser.  If this is unset
        then the parser used depends on whether blocks are being used.  If so,
        then the HideSolEolParser is used (so that you can specify tokens 
        without worrying about SOL and EOL); otherwise a normal parser is
        used.
        
        `discard` is a regular expression which is matched against the stream
        if lexing otherwise fails.  A successful match is discarded.  If None
        then the usual token defaut is used (whitespace).  To disable, use
        an empty string.
        
        `tabsize`, if not None, should be the number of spaces used to replace
        tabs.
        
        `block_policy` should be the number of spaces in an indent, if blocks 
        are used (or an appropriate function).  By default (ie if `block_start`
        is given) it is taken to be DEFAULT_POLICY.
        
        `block_start` is the initial indentation, if blocks are used.  By 
        default (ie if `block_policy` is given) 0 is used.
        
        To enable blocks ("offside rule" parsing), at least one of 
        `block_policy` and `block_start` must be given.
        `
        '''
        from lepl.offside.matchers import DEFAULT_TABSIZE
        from lepl.offside.regexp import LineAwareAlphabet, \
            make_hide_sol_eol_parser
        from lepl.offside.stream import LineAwareStreamFactory, \
            LineAwareTokenSource
        from lepl.regexp.str import make_str_parser
        from lepl.regexp.unicode import UnicodeAlphabet
        
        self.clear()
        
        use_blocks = block_policy is not None or block_start is not None
        if use_blocks:
            self.blocks(block_policy, block_start)
            
        if tabsize is None:
            tabsize = DEFAULT_TABSIZE
        if alphabet is None:
            alphabet = UnicodeAlphabet.instance()
        if not parser_factory:
            if use_blocks:
                parser_factory = make_hide_sol_eol_parser
            else:
                parser_factory = make_str_parser
        self.alphabet = LineAwareAlphabet(alphabet, parser_factory)

        self.set_alphabet_arg(self.alphabet)
        if use_blocks:
            self.set_block_policy_arg(block_policy)
        self.lexer(alphabet=self.alphabet, discard=discard, 
                   source=LineAwareTokenSource.factory(tabsize))
        self.stream_factory(LineAwareStreamFactory(self.alphabet))
        
        return self
        
    def default_line_aware(self, alphabet=None, parser_factory=None,
                           discard=None, tabsize=None, 
                           block_policy=None, block_start=None):
        '''
        Configure the parser for line aware behaviour.  This sets many 
        different options and is intended to be the "normal" way to enable
        line aware parsing (including "offside rule" support).
        
        Compared to `line_aware`, this also adds various "standard" options.
        
        Normally calling this method is all that is needed for configuration.
        If you do need to "fine tune" the configuration for parsing should
        consult the source for this method and then call other methods
        as needed.
        
        `alphabet` is the alphabet used; by default it is assumed to be Unicode
        and it will be extended to include start and end of line markers.
        
        `parser_factory` is used to generate a regexp parser.  If this is unset
        then the parser used depends on whether blocks are being used.  If so,
        then the HideSolEolParser is used (so that you can specify tokens 
        without worrying about SOL and EOL); otherwise a normal parser is
        used.
        
        `discard` is a regular expression which is matched against the stream
        if lexing otherwise fails.  A successful match is discarded.  If None
        then the usual token defaut is used (whitespace).  To disable, use
        an empty string.
        
        `tabsize`, if not None, should be the number of spaces used to replace
        tabs.
        
        `block_policy` should be the number of spaces in an indent, if blocks 
        are used (or an appropriate function).  By default (ie if `block_start`
        is given) it is taken to be DEFAULT_POLICY.
        
        `block_start` is the initial indentation, if blocks are used.  By 
        default (ie if `block_policy` is given) 0 is used.
        
        To enable blocks ("offside rule" parsing), at least one of 
        `block_policy` and `block_start` must be given.
        `
        '''
        self.line_aware(alphabet, parser_factory, discard, tabsize, 
                        block_policy, block_start)
        self.flatten()
        self.compose_transforms()
        self.auto_memoize()
        return self
        
    
    def clear(self):
        self.__unused = False
        self.__rewriters = []
        self.__monitors = []
        self.__stream_factory = DEFAULT_STREAM_FACTORY
        self.__alphabet = None
        return self

    def default(self):
        self.clear()
        self.flatten()
        self.compose_transforms()
        self.lexer()
        self.auto_memoize()
        self.trace()
        return self
        