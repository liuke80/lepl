
from logging import basicConfig, INFO

from lepl.match import *
from lepl.node import make_dict
from lepl.stream import Stream

basicConfig(level=INFO)
name    = Word()              >= 'name'
phone   = Integer()           >= 'phone'
line    = name / ',' / phone  >= make_dict
matcher = line[0:,~Newline()]
stream = Stream.from_string('andrew, 3333253\n bob, 12345', memory=(4,2,2))
print(next(matcher(stream)))
stream.core.bb.print_longest()

basicConfig(level=INFO)
name    = Word()                    >= 'name'
phone   = Trace(Integer(), 'phone') >= 'phone'
line    = name / ',' / phone        >= make_dict
matcher = line[0:,~Newline()]
print(matcher.parse_string('andrew, 3333253\n bob, 12345'))