# -*- coding: utf-8 -*-
"""生成访问口令的加密值：python tools/gen_hash.py 你的口令"""
import hashlib
import sys

if len(sys.argv) < 2:
    print("用法: python tools/gen_hash.py 你的口令")
else:
    print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())
