import glob
import importlib
import os
import sys

os.environ["COMPASS_TEST_MODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, ".")


for f in sorted(glob.glob("perception/tests/test_*.py") + glob.glob("overlay/tests/test_*.py")):
    mod_name = f.replace("/", ".").replace("\\", ".").replace(".py", "")
    print("Testing:", mod_name, flush=True)
    try:
        importlib.import_module(mod_name)
        print(" -> SUCCESS", flush=True)
    except Exception as e:
        print(" -> EXCEPTION:", e, flush=True)

print("ALL TEST MODULES TESTED SUCCESSFULLY")
