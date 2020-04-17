from hashlib import md5
from argparse import *

parser = ArgumentParser()
parser._action_groups.pop()
required = parser.add_argument_group('required arguments')
required.add_argument('-f', required=True, metavar='zipped project', type=FileType('r'), help='zipped project')
args = parser.parse_args()
zipped_project = args.f.name

m = md5()
with open(zipped_project, "rb") as f:
    data = f.read() 
    m.update(data)
    print(m.hexdigest())