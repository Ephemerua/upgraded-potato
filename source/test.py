from replayer import Replayer

rr = Replayer("./ptrace/stdin/tests/test", "./ptrace/stdin/tests/stdin.txt", "./ptrace/stdin/tests/maps.88499", test=True)

from parse_helpers import *

dumps = parse_dumps(rr, "./ptrace/stdin/tests/maps.88499.dump")

s = rr.get_entry_state()

simgr = rr.get_simgr()
simgr.run()