import sys


data = list(map(int, sys.stdin.buffer.read().split()))
count = data[0]
values = data[1:]
print(sum(values))
